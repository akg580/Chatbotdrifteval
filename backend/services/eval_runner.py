"""
eval_runner.py — Evaluation pipeline.

Windows / Python 3.9 compatible:
  - Cross-platform file lock (fcntl on POSIX, msvcrt on Windows)
  - No X | Y type hints — uses Optional from typing
  - No list[dict] PEP 585 generics
  - os.replace guarded with same-drive fallback for Windows cross-drive edge case
"""

import json
import logging
import os
import platform
import shutil
import tempfile
import requests
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from config import Config
from models.evaluator import LLMEvaluator
from services.dataset_generator import LLMClient
from services.pii_redactor import get_redactor

logger = logging.getLogger(__name__)

# ── Cross-platform file lock ─────────────────────────────────────────
if platform.system() == 'Windows':
    import msvcrt

    def _lock(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            pass   # Non-blocking lock — best effort on Windows

    def _unlock(f):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _lock(f):   fcntl.flock(f, fcntl.LOCK_EX)
    def _unlock(f): fcntl.flock(f, fcntl.LOCK_UN)

# ── Chatbot response extraction ──────────────────────────────────────
_RESPONSE_KEYS = ('response', 'message', 'reply', 'text', 'answer', 'content')


def _extract_bot_text(data):  # type: (dict) -> Optional[str]
    """Extract the text reply from a chatbot API response dict."""
    if not isinstance(data, dict):
        return None
    for key in _RESPONSE_KEYS:
        val = data.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return None


class EvalRunner:
    """Orchestrates the full evaluation pipeline."""

    def __init__(self):
        self.evaluator = LLMEvaluator()
        self.client    = LLMClient()
        self.redactor  = get_redactor()

    # ── Chatbot response ─────────────────────────────────────────────

    def simulate_chatbot_response(self, question):  # type: (str) -> str
        """Call the real bot or fall back to LLM simulation."""
        if Config.CHATBOT_ENDPOINT:
            result = self._call_real_chatbot(question)
            if result is not None:
                return result
            logger.warning("Real chatbot unavailable — using LLM simulation.")
        return self._llm_simulate(question)

    def _call_real_chatbot(self, question):  # type: (str) -> Optional[str]
        headers = {'Content-Type': 'application/json'}
        if Config.CHATBOT_API_KEY:
            headers['Authorization'] = 'Bearer ' + Config.CHATBOT_API_KEY

        try:
            resp = requests.post(
                Config.CHATBOT_ENDPOINT,
                json={'message': question},
                headers=headers,
                timeout=(Config.CHATBOT_CONNECT_TIMEOUT, Config.CHATBOT_READ_TIMEOUT),
            )
            resp.raise_for_status()

            try:
                data = resp.json()
            except ValueError:
                logger.error("Chatbot returned non-JSON (status=%d): %.200s",
                             resp.status_code, resp.text)
                return None

            text = _extract_bot_text(data)
            if text is None:
                logger.error("Chatbot response has no text field. Keys=%s Expected one of=%s",
                             list(data.keys()), _RESPONSE_KEYS)
                return None
            return text

        except requests.Timeout:
            logger.error("Chatbot timed out (%.0f/%.0fs connect/read)",
                         Config.CHATBOT_CONNECT_TIMEOUT, Config.CHATBOT_READ_TIMEOUT)
        except requests.HTTPError as exc:
            logger.error("Chatbot HTTP error: %s", exc)
        except requests.ConnectionError as exc:
            logger.error("Chatbot connection error: %s", exc)
        except Exception as exc:
            logger.exception("Unexpected chatbot error: %s", exc)
        return None

    def _llm_simulate(self, question):  # type: (str) -> str
        prompt = (
            "You are a customer service chatbot for a bank.\n"
            "Respond professionally and empathetically.\n"
            "Follow bank policies — never make unauthorized promises.\n"
            "Escalate fraud claims, loan approvals, and rate changes.\n\n"
            "CUSTOMER: " + question + "\n\n"
            "Provide ONLY the chatbot response, nothing else."
        )
        try:
            return self.client.generate(prompt, max_tokens=500, temperature=0.7).strip()
        except Exception as exc:
            logger.error("LLM simulation failed: %s", exc)
            return (
                "I apologize, but I'm experiencing technical difficulties. "
                "Please contact our support team."
            )

    # ── Evaluation pipeline ──────────────────────────────────────────

    def run_evaluation_suite(self, dataset, progress_callback=None):
        # type: (List[dict], Optional[Callable]) -> dict
        """Run a full evaluation on dataset, return structured result dict."""
        total = len(dataset)
        logger.info("Starting evaluation: %d questions, provider=%s", total, Config.LLM_PROVIDER)

        qa_pairs = []
        for i, item in enumerate(dataset):
            bot_response = self.simulate_chatbot_response(item['question'])
            qa_pairs.append({
                'id':           item.get('id', i + 1),
                'question':     item['question'],
                'bot_response': bot_response,
                'category':     item.get('category', 'general'),
                'risk_level':   item.get('risk_level', 'medium'),
                'timestamp':    datetime.now(timezone.utc).isoformat(),
            })

        results = self.evaluator.batch_evaluate(qa_pairs, progress_callback=progress_callback)
        metrics = self._calculate_metrics(results)

        return {
            'results':      results,
            'metrics':      metrics,
            'timestamp':    datetime.now(timezone.utc).isoformat(),
            'dataset_size': total,
            'provider':     Config.LLM_PROVIDER,
            'model':        Config.MODEL_NAME,
        }

    def _calculate_metrics(self, results):  # type: (List[dict]) -> dict
        if not results:
            return {}

        total   = len(results)
        valid   = [r for r in results if r['evaluation'].get('compliance_score') is not None]
        errors  = total - len(valid)
        n_valid = len(valid)

        if n_valid == 0:
            logger.error("All %d evaluations failed — no valid metrics.", total)
            return {
                'total_evaluations': total,
                'eval_error_count':  errors,
                'compliance_rate':   None,
                'avg_empathy_score': None,
            }

        compliant = sum(1 for r in valid if r['evaluation']['compliance_score'] == 1)
        empathy   = [r['evaluation']['empathy_score'] for r in valid]

        high_risk = [r for r in valid if r.get('risk_level') == 'high']
        hr_total  = len(high_risk)
        hr_ok     = sum(1 for r in high_risk if r['evaluation']['compliance_score'] == 1)

        total_flags = sum(len(r['evaluation'].get('flags', [])) for r in results)

        return {
            'total_evaluations':         total,
            'valid_evaluations':         n_valid,
            'eval_error_count':          errors,
            'compliance_rate':           round(compliant / n_valid, 3),
            'avg_empathy_score':         round(sum(empathy) / n_valid, 2),
            'compliant_count':           compliant,
            'non_compliant_count':       n_valid - compliant,
            'high_risk_compliance_rate': round(hr_ok / hr_total, 3) if hr_total > 0 else None,
            'high_risk_total':           hr_total,
            'total_flags':               total_flags,
            'empathy_distribution': {
                '5_star': sum(1 for s in empathy if s == 5),
                '4_star': sum(1 for s in empathy if s == 4),
                '3_star': sum(1 for s in empathy if s == 3),
                '2_star': sum(1 for s in empathy if s == 2),
                '1_star': sum(1 for s in empathy if s == 1),
            },
        }

    # ── Persistence (atomic write, cross-platform lock) ──────────────

    def save_results(self, eval_results, filepath=None):
        # type: (dict, Optional[str]) -> str
        """Append results atomically. Cross-platform safe on Windows + POSIX."""
        filepath  = filepath or Config.RESULTS_PATH
        lock_path = filepath + '.lock'

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(lock_path, 'w') as lock_f:
            _lock(lock_f)
            try:
                # Read existing
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        all_results = json.load(f)
                except FileNotFoundError:
                    all_results = {'evaluations': []}
                except json.JSONDecodeError:
                    logger.warning("Results file corrupt — starting fresh.")
                    all_results = {'evaluations': []}

                all_results['evaluations'].append(eval_results)

                # Write to temp file in same directory, then rename
                dir_name = os.path.dirname(os.path.abspath(filepath))
                fd, tmp = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as tf:
                        json.dump(all_results, tf, indent=2, ensure_ascii=False)
                    # os.replace is atomic on POSIX; on Windows it may fail
                    # if antivirus or another process holds the target — fallback to shutil
                    try:
                        os.replace(tmp, filepath)
                    except OSError:
                        shutil.move(tmp, filepath)
                except Exception:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    raise
            finally:
                _unlock(lock_f)

        return filepath

    def load_results(self, filepath=None):  # type: (Optional[str]) -> dict
        filepath = filepath or Config.RESULTS_PATH
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'evaluations': []}
        except json.JSONDecodeError as exc:
            logger.error("Results file corrupt: %s", exc)
            return {'evaluations': [], 'error': 'Results file corrupt'}

    def get_drift_data(self):  # type: () -> List[dict]
        """Return time-series data for the drift chart."""
        return [
            {
                'timestamp':                 run.get('timestamp'),
                'compliance_rate':           run.get('metrics', {}).get('compliance_rate'),
                'avg_empathy':               run.get('metrics', {}).get('avg_empathy_score'),
                'total_flags':               run.get('metrics', {}).get('total_flags'),
                'high_risk_compliance_rate': run.get('metrics', {}).get('high_risk_compliance_rate'),
                'eval_error_count':          run.get('metrics', {}).get('eval_error_count', 0),
            }
            for run in self.load_results().get('evaluations', [])
        ]