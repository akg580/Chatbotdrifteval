"""
db_storage.py — SQLite-backed persistence layer.
Python 3.9+ compatible. Windows + Linux/Mac safe.

Enable with USE_SQLITE=true in .env.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional

from config import Config

logger = logging.getLogger(__name__)


def _row_to_dict(row):
    # type: (sqlite3.Row) -> Dict
    """Convert sqlite3.Row to plain dict INSIDE the connection context."""
    return dict(row)


class DBStorage:
    """SQLite storage — concurrent-safe via WAL mode and foreign keys."""

    def __init__(self, db_path=None):
        # type: (Optional[str]) -> None
        self.db_path = db_path or Config.DB_PATH
        self._init_schema()

    @contextmanager
    def _get_conn(self):
        # type: () -> Generator[sqlite3.Connection, None, None]
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        # type: () -> None
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS eval_runs (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp    TEXT    NOT NULL,
                    dataset_size INTEGER,
                    provider     TEXT,
                    model        TEXT,
                    metrics      TEXT    NOT NULL,
                    created_at   TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS eval_results (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id       INTEGER NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
                    question_id  TEXT,
                    question     TEXT    NOT NULL,
                    bot_response TEXT    NOT NULL,
                    risk_level   TEXT,
                    category     TEXT,
                    timestamp    TEXT,
                    evaluation   TEXT    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_eval_results_run
                    ON eval_results(run_id);
                CREATE INDEX IF NOT EXISTS idx_eval_runs_ts
                    ON eval_runs(timestamp);
            """)

    def save_eval_run(self, eval_results):
        # type: (dict) -> int
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO eval_runs (timestamp, dataset_size, provider, model, metrics)"
                " VALUES (?,?,?,?,?)",
                (
                    eval_results.get('timestamp',
                                     datetime.now(timezone.utc).isoformat()),
                    eval_results.get('dataset_size', 0),
                    eval_results.get('provider', Config.LLM_PROVIDER),
                    eval_results.get('model',    Config.MODEL_NAME),
                    json.dumps(eval_results.get('metrics', {})),
                ),
            )
            run_id = cur.lastrowid

            rows = [
                (
                    run_id,
                    str(r.get('id', '')),
                    r.get('question', ''),
                    r.get('bot_response', ''),
                    r.get('risk_level', 'medium'),
                    r.get('category', 'general'),
                    r.get('timestamp', ''),
                    json.dumps(r.get('evaluation', {})),
                )
                for r in eval_results.get('results', [])
            ]
            conn.executemany(
                "INSERT INTO eval_results"
                " (run_id, question_id, question, bot_response,"
                "  risk_level, category, timestamp, evaluation)"
                " VALUES (?,?,?,?,?,?,?,?)",
                rows,
            )
        logger.info("Saved eval run id=%d (%d results)", run_id, len(rows))
        return run_id

    def load_all_runs(self):
        # type: () -> dict
        with self._get_conn() as conn:
            runs = [_row_to_dict(r) for r in
                    conn.execute("SELECT * FROM eval_runs ORDER BY id ASC").fetchall()]
            evaluations = []
            for run in runs:
                result_rows = [_row_to_dict(r) for r in
                               conn.execute(
                                   "SELECT * FROM eval_results WHERE run_id=?",
                                   (run['id'],)
                               ).fetchall()]
                evaluations.append({
                    'timestamp':    run['timestamp'],
                    'dataset_size': run['dataset_size'],
                    'provider':     run.get('provider'),
                    'model':        run.get('model'),
                    'metrics':      json.loads(run['metrics']),
                    'results':      [self._result_to_dict(r) for r in result_rows],
                })
        return {'evaluations': evaluations}

    def load_latest_run(self):
        # type: () -> Optional[dict]
        with self._get_conn() as conn:
            run_row = conn.execute(
                "SELECT * FROM eval_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not run_row:
                return None
            run = _row_to_dict(run_row)
            result_rows = [_row_to_dict(r) for r in
                           conn.execute(
                               "SELECT * FROM eval_results WHERE run_id=?",
                               (run['id'],)
                           ).fetchall()]
        return {
            'timestamp':    run['timestamp'],
            'dataset_size': run['dataset_size'],
            'provider':     run.get('provider'),
            'model':        run.get('model'),
            'metrics':      json.loads(run['metrics']),
            'results':      [self._result_to_dict(r) for r in result_rows],
        }

    def get_drift_data(self):
        # type: () -> List[dict]
        with self._get_conn() as conn:
            rows = [_row_to_dict(r) for r in
                    conn.execute(
                        "SELECT timestamp, provider, model, metrics"
                        " FROM eval_runs ORDER BY id ASC"
                    ).fetchall()]
        drift = []
        for row in rows:
            m = json.loads(row['metrics'])
            drift.append({
                'timestamp':                 row['timestamp'],
                'provider':                  row.get('provider'),
                'compliance_rate':           m.get('compliance_rate'),
                'avg_empathy':               m.get('avg_empathy_score'),
                'total_flags':               m.get('total_flags'),
                'high_risk_compliance_rate': m.get('high_risk_compliance_rate'),
                'eval_error_count':          m.get('eval_error_count', 0),
            })
        return drift

    def count_runs(self):
        # type: () -> int
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM eval_runs").fetchone()[0]

    @staticmethod
    def _result_to_dict(row):
        # type: (dict) -> dict
        return {
            'id':           row['question_id'],
            'question':     row['question'],
            'bot_response': row['bot_response'],
            'risk_level':   row['risk_level'],
            'category':     row['category'],
            'timestamp':    row['timestamp'],
            'evaluation':   json.loads(row['evaluation']),
        }