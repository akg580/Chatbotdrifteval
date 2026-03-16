"""
pii_redactor.py — PII redaction before text reaches any LLM provider.
Python 3.9+ compatible. Windows + Linux/Mac safe.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PIIPattern:
    name:        str
    pattern:     re.Pattern   # type: ignore[type-arg]
    placeholder: str
    priority:    int = 0


_PATTERNS: List[PIIPattern] = [
    # IBAN (before sort codes — overlapping digit runs)
    PIIPattern(
        name='iban',
        pattern=re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b'),
        placeholder='[IBAN]',
        priority=11,
    ),
    # 16/15-digit payment cards — before phone
    PIIPattern(
        name='card_number',
        pattern=re.compile(
            r'\b(?:4[0-9]{3}|5[1-5][0-9]{2}|3[47][0-9]{2}|6(?:011|5[0-9]{2}))'
            r'[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3,4}\b'
        ),
        placeholder='[CARD]',
        priority=10,
    ),
    # UK sort code — requires separator (not bare 6 digits)
    PIIPattern(
        name='sort_code',
        pattern=re.compile(r'\b\d{2}[-\s]\d{2}[-\s]\d{2}\b'),
        placeholder='[SORT-CODE]',
        priority=9,
    ),
    # US SSN — hyphen form only (bare 9-digit too broad)
    PIIPattern(
        name='ssn',
        pattern=re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        placeholder='[SSN]',
        priority=9,
    ),
    # Email
    PIIPattern(
        name='email',
        pattern=re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'),
        placeholder='[EMAIL]',
        priority=8,
    ),
    # Phone — 10+ digit domestic or international
    PIIPattern(
        name='phone',
        pattern=re.compile(
            r'(?:'
            r'\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
            r'|0\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
            r'|\(\d{3,4}\)[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
            r')'
        ),
        placeholder='[PHONE]',
        priority=7,
    ),
    # Bank account numbers — 6–12 digit standalone
    PIIPattern(
        name='account_number',
        pattern=re.compile(r'\b\d{6,12}\b'),
        placeholder='[ACCT]',
        priority=5,
    ),
    # Salutation-based names
    PIIPattern(
        name='full_name',
        pattern=re.compile(
            r'\b(?:Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.?|Prof\.?)\s+'
            r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b'
        ),
        placeholder='[NAME]',
        priority=4,
    ),
]

_PATTERNS.sort(key=lambda p: p.priority, reverse=True)


class PIIRedactor:
    """Redacts PII from text before it is sent to any external LLM API."""

    def redact(self, text):
        # type: (str) -> Tuple[str, Dict[str, str]]
        """
        Replace PII with stable hash-tagged placeholders.

        Returns (clean_text, mapping).
        NEVER log the mapping — it contains original PII.
        """
        if not text or not text.strip():
            return text, {}

        clean   = text
        mapping = {}  # type: Dict[str, str]

        for pat in _PATTERNS:
            def _replace(m, _pat=pat):
                # type: (re.Match[str], PIIPattern) -> str
                original = m.group(0)
                suffix   = hashlib.md5(original.encode()).hexdigest()[:4].upper()
                key      = '[{}-{}]'.format(_pat.name.upper(), suffix)
                mapping.setdefault(key, original)
                return key
            clean = pat.pattern.sub(_replace, clean)

        if mapping:
            logger.debug("PII redacted: %s", self.audit_summary(mapping))

        return clean, mapping

    def redact_batch(self, texts):
        # type: (List[str]) -> Tuple[List[str], List[Dict[str, str]]]
        results = [self.redact(t) for t in texts]
        return [r[0] for r in results], [r[1] for r in results]

    @staticmethod
    def audit_summary(mapping):
        # type: (Dict[str, str]) -> Dict[str, int]
        """Return type counts only — safe to log."""
        counts = {}  # type: Dict[str, int]
        for key in mapping:
            ptype = key.lstrip('[').split('-')[0]
            counts[ptype] = counts.get(ptype, 0) + 1
        return counts


_default_redactor = None  # type: Optional[PIIRedactor]


def get_redactor():
    # type: () -> PIIRedactor
    global _default_redactor
    if _default_redactor is None:
        _default_redactor = PIIRedactor()
    return _default_redactor