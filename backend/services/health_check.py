"""
health_check.py - Lightweight dependency checks for /health/detail.
"""

import os
import time
from dataclasses import dataclass
from typing import List

from config import Config
from services.dataset_generator import LLMClient


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    latency_ms: float = 0.0

    def to_dict(self):
        return {
            'name': self.name,
            'ok': self.ok,
            'detail': self.detail,
            'latency_ms': self.latency_ms,
        }


class HealthChecker:
    def __init__(self):
        self._client = LLMClient()

    def run_all(self, include_llm_probe=False):  # type: (bool) -> List[CheckResult]
        results = []

        results.append(self._check_data_dir())
        results.append(self._check_results_path())

        if include_llm_probe:
            results.append(self._check_llm())

        return results

    def _check_data_dir(self):
        start = time.time()
        try:
            os.makedirs('data', exist_ok=True)
            test_path = os.path.join('data', '.health_check.tmp')
            with open(test_path, 'w', encoding='utf-8') as f:
                f.write('ok')
            os.remove(test_path)
            return CheckResult('data_dir', True, 'data/ writable', (time.time() - start) * 1000)
        except Exception as exc:
            return CheckResult('data_dir', False, f'data/ not writable: {exc}', (time.time() - start) * 1000)

    def _check_results_path(self):
        start = time.time()
        try:
            base = os.path.dirname(os.path.abspath(Config.RESULTS_PATH))
            os.makedirs(base, exist_ok=True)
            return CheckResult('results_path', True, 'results path OK', (time.time() - start) * 1000)
        except Exception as exc:
            return CheckResult('results_path', False, f'results path error: {exc}', (time.time() - start) * 1000)

    def _check_llm(self):
        start = time.time()
        try:
            _ = self._client.generate("Ping", max_tokens=1, temperature=0)
            return CheckResult('llm', True, f'provider={Config.LLM_PROVIDER}', (time.time() - start) * 1000)
        except Exception as exc:
            return CheckResult('llm', False, f'LLM probe failed: {exc}', (time.time() - start) * 1000)


_checker = None


def get_checker():  # type: () -> HealthChecker
    global _checker
    if _checker is None:
        _checker = HealthChecker()
    return _checker
