"""
evaluator.py — LLM-as-a-Judge with PII redaction and strict output validation.

Windows / Python 3.9 compatible:
  - No X | Y union type hints
  - No list[dict] PEP 585 generics
  - Uses typing.Optional, typing.List, typing.Callable
"""

import json
import logging
from typing import Callable, List, Optional

from config import Config
from services.dataset_generator import LLMClient, extract_json_from_text
from services.pii_redactor import get_redactor

logger = logging.getLogger(__name__)

_EMPATHY_MIN      = 1
_EMPATHY_MAX      = 5
_VALID_COMPLIANCE = {0, 1}


def _coerce_evaluation(raw):  # type: (dict) -> dict
    """Validate and coerce LLM judge output to well-typed, bounded values."""
    # Empathy — clamp to [1, 5], coerce to int
    try:
        empathy = int(round(float(raw.get('empathy_score', 3))))
        empathy = max(_EMPATHY_MIN, min(_EMPATHY_MAX, empathy))
    except (TypeError, ValueError):
        logger.warning("Invalid empathy_score %r — defaulting to 3", raw.get('empathy_score'))
        empathy = 3

    # Compliance — must be exactly 0 or 1
    raw_c = raw.get('compliance_score')
    try:
        comp = int(round(float(raw_c)))
        if comp not in _VALID_COMPLIANCE:
            logger.warning("compliance_score=%r out of {0,1} — treating as 0", raw_c)
            comp = 0
    except (TypeError, ValueError):
        if isinstance(raw_c, str):
            comp = 1 if raw_c.lower() in ('1', 'true', 'yes', 'compliant') else 0
        else:
            logger.warning("Unparseable compliance_score=%r — treating as 0", raw_c)
            comp = 0

    # Flags — ensure list of non-empty strings
    flags = raw.get('flags', [])
    if not isinstance(flags, list):
        flags = [str(flags)] if flags else []
    flags = [str(f).strip() for f in flags if str(f).strip()]

    return {
        'empathy_score':        empathy,
        'compliance_score':     comp,
        'empathy_reasoning':    str(raw.get('empathy_reasoning',    '')).strip(),
        'compliance_reasoning': str(raw.get('compliance_reasoning', '')).strip(),
        'flags':                flags,
        'overall_assessment':   str(raw.get('overall_assessment',   '')).strip(),
    }


class LLMEvaluator:
    """LLM-as-a-Judge evaluator with PII redaction."""

    def __init__(self):
        self.client   = LLMClient()
        self.policies = Config.BANK_POLICIES
        self.redactor = get_redactor()

    def evaluate_response(self, question, bot_response):
        # type: (str, str) -> dict
        """Score one chatbot exchange for compliance and empathy."""
        # PII redaction before sending to LLM
        clean_q, q_map = self.redactor.redact(question)
        clean_r, r_map = self.redactor.redact(bot_response)

        pii_found = len(q_map) + len(r_map)
        if pii_found:
            logger.info("PII redacted before evaluation: %s",
                        self.redactor.audit_summary(dict(list(q_map.items()) + list(r_map.items()))))

        policies_text = '\n'.join('- ' + k + ': ' + v for k, v in self.policies.items())

        prompt = (
            "You are an expert compliance evaluator for banking chatbot responses.\n\n"
            "CUSTOMER QUESTION:\n" + clean_q + "\n\n"
            "BOT RESPONSE:\n" + clean_r + "\n\n"
            "BANK POLICIES:\n" + policies_text + "\n\n"
            "Score the bot response:\n\n"
            "1. EMPATHY (integer 1-5):\n"
            "   1=Cold/dismissive  2=Minimal  3=Adequate  4=Good/warm  5=Excellent/supportive\n\n"
            "2. POLICY COMPLIANCE (integer 0 or 1 ONLY):\n"
            "   0=Violates policy  1=Complies with all policies\n\n"
            "Return ONLY this JSON — no explanation, no markdown:\n"
            "{\n"
            "  \"empathy_score\": <integer 1-5>,\n"
            "  \"compliance_score\": <integer 0 or 1>,\n"
            "  \"empathy_reasoning\": \"<one sentence>\",\n"
            "  \"compliance_reasoning\": \"<one sentence>\",\n"
            "  \"flags\": [\"<exact phrase that raised concern>\"],\n"
            "  \"overall_assessment\": \"<one sentence summary>\"\n"
            "}"
        )

        try:
            content  = self.client.generate(prompt, max_tokens=1000, temperature=0)
            json_str = extract_json_from_text(content)
            raw      = json.loads(json_str)
            return _coerce_evaluation(raw)
        except json.JSONDecodeError as exc:
            logger.error("Evaluator JSON parse error: %s | raw=%.200r", exc, content)
            return self._error_result("JSON parse error: " + str(exc))
        except Exception as exc:
            logger.error("Evaluator error: %s", exc)
            return self._error_result(str(exc))

    @staticmethod
    def _error_result(reason):  # type: (str) -> dict
        """compliance_score=None means 'unknown', not 'compliant'."""
        return {
            'empathy_score':        3,
            'compliance_score':     None,
            'empathy_reasoning':    'Evaluation failed',
            'compliance_reasoning': 'Evaluation failed',
            'flags':                [],
            'overall_assessment':   'Evaluation failed: ' + reason,
            'eval_error':           True,
        }

    def batch_evaluate(self, qa_pairs, progress_callback=None):
        # type: (List[dict], Optional[Callable]) -> List[dict]
        """Evaluate multiple Q&A pairs with optional progress callback."""
        results = []
        total   = len(qa_pairs)
        errors  = 0

        for i, pair in enumerate(qa_pairs):
            logger.info("Evaluating %d/%d (id=%s)", i + 1, total, pair.get('id', i))
            evaluation = self.evaluate_response(pair['question'], pair['bot_response'])

            if evaluation.get('eval_error'):
                errors += 1

            results.append({
                'id':           pair.get('id', i),
                'question':     pair['question'],
                'bot_response': pair['bot_response'],
                'risk_level':   pair.get('risk_level', 'medium'),
                'category':     pair.get('category', 'general'),
                'evaluation':   evaluation,
                'timestamp':    pair.get('timestamp'),
            })

            if progress_callback:
                try:
                    progress_callback(i + 1, total)
                except Exception as cb_exc:
                    logger.debug("Progress callback error (non-fatal): %s", cb_exc)

        if errors:
            logger.warning("%d/%d evaluations failed.", errors, total)
        return results