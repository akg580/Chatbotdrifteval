"""
job_queue.py — In-process async job queue for long-running eval jobs.

Windows / Python 3.9 compatible:
  - No X | Y union type hints
  - No list[dict] PEP 585 generics
  - Future annotation uses string literal to avoid import-time resolution
"""

import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobState(str, Enum):
    PENDING   = 'pending'
    RUNNING   = 'running'
    DONE      = 'done'
    FAILED    = 'failed'
    CANCELLED = 'cancelled'


def _now():  # type: () -> str
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id:          str
    state:       JobState           = JobState.PENDING
    created_at:  str                = field(default_factory=_now)
    started_at:  Optional[str]      = None
    finished_at: Optional[str]      = None
    result:      Optional[Any]      = None
    error:       Optional[str]      = None
    progress:    int                = 0
    total_items: int                = 0
    done_items:  int                = 0
    # Use Any for Future to stay compatible with Python 3.9 dataclass field typing
    _future:     Any                = field(default=None, repr=False, compare=False)

    def to_dict(self):  # type: () -> dict
        return {
            'id':           self.id,
            'state':        self.state.value,
            'created_at':   self.created_at,
            'started_at':   self.started_at,
            'finished_at':  self.finished_at,
            'progress':     self.progress,
            'total_items':  self.total_items,
            'done_items':   self.done_items,
            'error':        self.error,
        }


class EvalJobQueue:
    """Thread-safe job queue backed by a ThreadPoolExecutor."""

    MAX_WORKERS:     int = 1
    MAX_STORED_JOBS: int = 200

    def __init__(self):
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix='eval-worker',
        )
        self._jobs  = {}   # type: Dict[str, Job]
        self._lock  = threading.Lock()
        logger.info("EvalJobQueue ready (max_workers=%d)", self.MAX_WORKERS)

    def submit(self, fn, *args, **kwargs):
        # type: (Callable, ...) -> str
        """Submit fn(*args, **kwargs) as a background job. Returns job ID."""
        dataset_size = kwargs.pop('dataset_size', 0)
        job_id = str(uuid.uuid4())[:12]
        job    = Job(id=job_id, total_items=dataset_size)

        with self._lock:
            self._prune_old_jobs()
            self._jobs[job_id] = job

        future = self._executor.submit(self._run_job, job_id, fn, *args, **kwargs)
        job._future = future

        logger.info("Job %s submitted (dataset_size=%d)", job_id, dataset_size)
        return job_id

    def get_status(self, job_id):  # type: (str) -> Optional[dict]
        with self._lock:
            job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def get_result(self, job_id):  # type: (str) -> Optional[Any]
        with self._lock:
            job = self._jobs.get(job_id)
        if job and job.state == JobState.DONE:
            return job.result
        return None

    def cancel(self, job_id):  # type: (str) -> bool
        with self._lock:
            job = self._jobs.get(job_id)
        if job and job._future and job._future.cancel():
            with self._lock:
                job.state       = JobState.CANCELLED
                job.finished_at = _now()
            logger.info("Job %s cancelled", job_id)
            return True
        return False

    def list_jobs(self, limit=50):  # type: (int) -> List[dict]
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    def update_progress(self, job_id, done, total):
        # type: (str, int, int) -> None
        with self._lock:
            job = self._jobs.get(job_id)
        if job:
            job.done_items  = done
            job.total_items = total
            job.progress    = int((done / max(total, 1)) * 100)

    def _run_job(self, job_id, fn, *args, **kwargs):
        # type: (str, Callable, ...) -> None
        with self._lock:
            job            = self._jobs[job_id]
            job.state      = JobState.RUNNING
            job.started_at = _now()

        logger.info("Job %s started", job_id)
        try:
            result = fn(*args, **kwargs)
            with self._lock:
                job.state       = JobState.DONE
                job.result      = result
                job.progress    = 100
                job.finished_at = _now()
            # Calculate duration safely
            try:
                start = datetime.fromisoformat(job.started_at.rstrip('Z'))
                end   = datetime.fromisoformat(job.finished_at.rstrip('Z'))
                logger.info("Job %s completed in %.1fs", job_id, (end - start).total_seconds())
            except Exception:
                logger.info("Job %s completed", job_id)
        except Exception as exc:
            with self._lock:
                job.state       = JobState.FAILED
                job.error       = str(exc)
                job.finished_at = _now()
            logger.error("Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())

    def _prune_old_jobs(self):
        # type: () -> None
        """Remove oldest jobs beyond MAX_STORED_JOBS. Must be called inside _lock."""
        if len(self._jobs) >= self.MAX_STORED_JOBS:
            oldest   = sorted(self._jobs.items(), key=lambda kv: kv[1].created_at)
            to_prune = len(self._jobs) - self.MAX_STORED_JOBS + 1
            for job_id, _ in oldest[:to_prune]:
                del self._jobs[job_id]
            logger.debug("Pruned %d old jobs from queue", to_prune)

    def shutdown(self, wait=True):  # type: (bool) -> None
        logger.info("Shutting down EvalJobQueue (wait=%s)…", wait)
        self._executor.shutdown(wait=wait)


# ── Module-level singleton ────────────────────────────────────────────
_queue = None  # type: Optional[EvalJobQueue]


def get_queue():  # type: () -> EvalJobQueue
    """Return the shared EvalJobQueue instance."""
    global _queue
    if _queue is None:
        _queue = EvalJobQueue()
    return _queue