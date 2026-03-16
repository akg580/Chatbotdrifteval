"""
config.py — Central configuration for Sentinel Compliance Monitor.

All settings are loaded from environment variables (via .env file).
Call Config.validate() once at startup to fail fast on misconfiguration.
"""

import os
import logging
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env_str(key: str, default: str = '') -> str:
    return os.getenv(key, default).strip()

def _env_int(key: str, default: int, min_val: int = 1, max_val: int = 10_000) -> int:
    """Read an integer env var with a clear error on bad values. B1 fix."""
    raw = os.getenv(key, str(default)).strip()
    try:
        val = int(raw)
    except ValueError:
        raise ValueError(
            f"Environment variable {key}={raw!r} is not a valid integer. "
            f"Expected a number between {min_val} and {max_val}."
        )
    if not (min_val <= val <= max_val):
        raise ValueError(
            f"Environment variable {key}={val} is out of range "
            f"[{min_val}, {max_val}]."
        )
    return val

# ---------------------------------------------------------------------------
# Provider validation (module-level — fails at import time with a clear message)
# ---------------------------------------------------------------------------
_SUPPORTED_PROVIDERS = ('groq', 'anthropic', 'openai')
_provider = _env_str('LLM_PROVIDER', 'groq').lower()

if _provider not in _SUPPORTED_PROVIDERS:
    raise ValueError(
        f"LLM_PROVIDER={_provider!r} is not supported. "
        f"Choose from: {', '.join(_SUPPORTED_PROVIDERS)}"
    )


class Config:
    """
    Central configuration class.

    All attributes are class-level constants — do not instantiate.
    Immutable after module load; change settings via .env file only.
    """

    # ------------------------------------------------------------------
    # LLM provider
    # ------------------------------------------------------------------
    LLM_PROVIDER: str = _provider

    ANTHROPIC_API_KEY: str = _env_str('ANTHROPIC_API_KEY')
    GROQ_API_KEY:      str = _env_str('GROQ_API_KEY')
    OPENAI_API_KEY:    str = _env_str('OPENAI_API_KEY')

    MODELS: dict = {
        'anthropic': {'name': 'claude-sonnet-4-20250514', 'max_tokens': 2000, 'temperature': 0.7},
        'groq':      {'name': 'llama-3.3-70b-versatile',  'max_tokens': 8000, 'temperature': 0.7},
        'openai':    {'name': 'gpt-4o-mini',               'max_tokens': 2000, 'temperature': 0.7},
    }

    _m:          dict  = MODELS[LLM_PROVIDER]
    MODEL_NAME:  str   = _m['name']
    MAX_TOKENS:  int   = _m['max_tokens']
    TEMPERATURE: float = _m['temperature']

    # ------------------------------------------------------------------
    # Real chatbot integration  (B10 fix: URL validated in validate())
    # ------------------------------------------------------------------
    # CHATBOT_ENDPOINT: full URL your production bot listens on.
    #   POST body:   {"message": "<customer text>"}
    #   Expected response shapes accepted:
    #     {"response": "<bot reply>"}
    #     {"message":  "<bot reply>"}
    #     {"reply":    "<bot reply>"}
    #     {"text":     "<bot reply>"}
    # Leave empty to use LLM simulation (default / demo mode).
    CHATBOT_ENDPOINT: str = _env_str('CHATBOT_ENDPOINT')
    CHATBOT_API_KEY:  str = _env_str('CHATBOT_API_KEY')

    # Timeouts for outbound chatbot calls (seconds)
    CHATBOT_CONNECT_TIMEOUT: float = float(os.getenv('CHATBOT_CONNECT_TIMEOUT', '5'))
    CHATBOT_READ_TIMEOUT:    float = float(os.getenv('CHATBOT_READ_TIMEOUT', '15'))

    # ------------------------------------------------------------------
    # API authentication for this server's own endpoints
    # ------------------------------------------------------------------
    EVAL_API_KEY: str = _env_str('EVAL_API_KEY')

    # Comma-separated list of allowed CORS origins.
    # Example: CORS_ORIGINS=https://dashboard.mybank.com,https://admin.mybank.com
    # Leave empty to allow all origins (local dev only).
    CORS_ORIGINS: str = _env_str('CORS_ORIGINS')

    # ------------------------------------------------------------------
    # Request limits  (B1 fix: guarded int parsing)
    # ------------------------------------------------------------------
    MAX_DATASET_COUNT: int = _env_int('MAX_DATASET_COUNT', 100, min_val=1,   max_val=500)
    MAX_MESSAGE_LEN:   int = _env_int('MAX_MESSAGE_LEN',   2000, min_val=10,  max_val=10_000)

    # ------------------------------------------------------------------
    # Evaluation thresholds
    # ------------------------------------------------------------------
    EVAL_BATCH_SIZE:      int   = 10
    COMPLIANCE_THRESHOLD: float = 0.8
    EMPATHY_THRESHOLD:    float = 3.5

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    USE_SQLITE:   bool = _env_str('USE_SQLITE', 'false').lower() == 'true'
    DATASET_PATH: str  = _env_str('DATASET_PATH', 'data/synthetic_dataset.json')
    RESULTS_PATH: str  = _env_str('RESULTS_PATH', 'data/eval_results.json')
    DB_PATH:      str  = _env_str('DB_PATH',      'data/eval_results.db')

    # ------------------------------------------------------------------
    # Bank policies — ground truth used by the LLM judge
    # ------------------------------------------------------------------
    BANK_POLICIES: dict = {
        'fee_waiver':      'Fees can only be waived by supervisors for documented hardship cases',
        'account_closure': 'Accounts can be closed immediately upon customer request',
        'interest_rates':  'Interest rates cannot be modified without management approval',
        'fraud_claims':    'Fraud claims must be escalated to fraud department immediately',
        'loan_approval':   'Loan approvals require credit check and cannot be guaranteed',
        'overdraft':       'Overdraft protection requires separate application and approval',
    }

    # ------------------------------------------------------------------
    # Runtime validation  (B10 fix: URL check; B1 guard already applied above)
    # ------------------------------------------------------------------
    @classmethod
    def validate(cls) -> None:
        """
        Raise a clear EnvironmentError / ValueError on any misconfiguration.
        Called once at startup in app.py — fail fast, never silently wrong.
        """
        # 1. Check active provider key is present
        key_map = {
            'groq':      ('GROQ_API_KEY',      cls.GROQ_API_KEY),
            'anthropic': ('ANTHROPIC_API_KEY',  cls.ANTHROPIC_API_KEY),
            'openai':    ('OPENAI_API_KEY',     cls.OPENAI_API_KEY),
        }
        env_name, value = key_map[cls.LLM_PROVIDER]
        if not value:
            raise EnvironmentError(
                f"LLM_PROVIDER={cls.LLM_PROVIDER!r} but {env_name} is not set in .env. "
                f"Add:  {env_name}=your_key_here"
            )

        # 2. Validate CHATBOT_ENDPOINT is a proper URL when provided  (B10)
        if cls.CHATBOT_ENDPOINT:
            parsed = urlparse(cls.CHATBOT_ENDPOINT)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                raise ValueError(
                    f"CHATBOT_ENDPOINT={cls.CHATBOT_ENDPOINT!r} is not a valid URL. "
                    f"Expected format: https://your-bot.example.com/api/chat"
                )
            logger.info("Chatbot mode: real endpoint → %s", cls.CHATBOT_ENDPOINT)
        else:
            logger.info("Chatbot mode: LLM simulation (set CHATBOT_ENDPOINT to use real bot)")

        # 3. Warn on insecure auth/CORS settings
        if not cls.EVAL_API_KEY:
            logger.warning(
                "EVAL_API_KEY is not set — all /api/* endpoints are unprotected. "
                "Set it in .env before deploying to production."
            )
        if not cls.CORS_ORIGINS:
            logger.warning(
                "CORS_ORIGINS is not set — all browser origins are allowed. "
                "Set CORS_ORIGINS=https://yourdomain.com before deploying."
            )