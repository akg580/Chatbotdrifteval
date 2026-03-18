"""
app.py — Sentinel Compliance Monitor API v2.0
Production-ready. Python 3.9+ compatible. Windows + Linux/Mac.

Hosting:
  Backend  → Render.com (free tier)
  Frontend → Netlify (free tier, static files)
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import List

from flask import Flask, jsonify, request, g
from flask_cors import CORS

from config import Config
from services.dataset_generator import DatasetGenerator
from services.eval_runner import EvalRunner
from services.job_queue import get_queue, JobState
from services.health_check import get_checker

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
)
logger = logging.getLogger(__name__)

# ── Startup validation ────────────────────────────────────────────────
Config.validate()

_run_llm_probe = os.getenv('SKIP_LLM_PROBE', '0') != '1'
_startup_health = get_checker().run_all(include_llm_probe=_run_llm_probe)
for _r in _startup_health:
    _level = logging.INFO if _r.ok else logging.WARNING
    logger.log(_level, "Startup check [%s]: %s%s",
               _r.name, _r.detail,
               "  ({:.0f}ms)".format(_r.latency_ms) if _r.latency_ms else "")

# ── Flask + CORS ──────────────────────────────────────────────────────
app = Flask(__name__)

if Config.CORS_ORIGINS:
    # FIX: strip trailing slashes — Render env vars often have them
    _origins = [o.strip().rstrip('/') for o in Config.CORS_ORIGINS.split(',') if o.strip()]
    CORS(app,
         origins=_origins,
         supports_credentials=False,
         allow_headers=['Content-Type', 'X-API-Key', 'X-Request-ID'],
         methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
    logger.info("CORS restricted to: %s", _origins)
else:
    CORS(app,
         allow_headers=['Content-Type', 'X-API-Key', 'X-Request-ID'],
         methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
    logger.warning("CORS open to all origins — set CORS_ORIGINS for production")

# ── Services ──────────────────────────────────────────────────────────
dataset_gen = DatasetGenerator()
eval_runner = EvalRunner()
queue       = get_queue()
os.makedirs('data', exist_ok=True)

# Limit request body to 5MB — prevents memory exhaustion on large payloads
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB


# ── Explicit OPTIONS handler for CORS preflight ──────────────────────
# Some proxies / hosting platforms strip CORS headers unless OPTIONS
# is explicitly handled. Flask-CORS normally handles this, but this
# is a belt-and-suspenders guarantee.
@app.route('/api/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return '', 204


# ── Request lifecycle ─────────────────────────────────────────────────

@app.before_request
def assign_request_id():
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4())[:8])


@app.after_request
def add_security_headers(response):
    response.headers['X-Request-ID']        = getattr(g, 'request_id', '-')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']       = 'DENY'
    response.headers['Cache-Control']         = 'no-store'
    return response


# ── Authentication ────────────────────────────────────────────────────

def require_api_key(f):
    """Enforce X-API-Key header when EVAL_API_KEY is configured."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.EVAL_API_KEY:
            return f(*args, **kwargs)
        key = request.headers.get('X-API-Key', '')
        if not key or key != Config.EVAL_API_KEY:
            logger.warning("Unauthorized: %s %s from %s",
                           request.method, request.path, request.remote_addr)
            return jsonify({'success': False,
                            'error': 'Unauthorized: invalid or missing X-API-Key'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Error handlers ────────────────────────────────────────────────────

@app.errorhandler(400)
def bad_request(exc):
    return jsonify({'success': False, 'error': 'Bad request'}), 400


@app.errorhandler(413)
def request_too_large(exc):
    return jsonify({'success': False, 'error': 'Request body exceeds 5MB limit'}), 413


@app.errorhandler(404)
def not_found(exc):
    return jsonify({'success': False, 'error': 'Not found'}), 404


@app.errorhandler(405)
def method_not_allowed(exc):
    return jsonify({'success': False, 'error': 'Method not allowed'}), 405


@app.errorhandler(500)
def internal_error(exc):
    logger.exception("Unhandled exception")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ═════════════════════════════════════════════════════════════════════
# ROUTES
# ═════════════════════════════════════════════════════════════════════

# ── System ────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health_simple():
    """Render.com / uptime-robot ping — fast, no I/O."""
    return jsonify({
        'status':    'ok',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/health/detail', methods=['GET'])
def health_detail():
    """Full dependency health — use ?probe=1 to include live LLM call."""
    probe   = request.args.get('probe', '0') == '1'
    results = get_checker().run_all(include_llm_probe=probe)
    all_ok  = all(r.ok for r in results)
    return jsonify({
        'status':    'ok' if all_ok else 'degraded',
        'checks':    [r.to_dict() for r in results],
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200 if all_ok else 503


@app.route('/')
def home():
    return jsonify({
        'service':       'Sentinel Compliance Monitor',
        'version':       '2.0',
        'auth':          'enabled' if Config.EVAL_API_KEY else 'disabled (dev)',
        'chatbot_mode':  'real endpoint' if Config.CHATBOT_ENDPOINT else 'LLM simulation',
        'provider':      Config.LLM_PROVIDER,
        'model':         Config.MODEL_NAME,
        'pii_redaction': 'enabled',
    })


# ── Chat ──────────────────────────────────────────────────────────────

@app.route('/api/chat', methods=['POST'])
@require_api_key
def chat():
    """Live chat + real-time compliance/empathy evaluation."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'success': False,
                        'error': 'Request body must be a JSON object'}), 400

    message = str(data.get('message', '')).strip()
    if not message:
        return jsonify({'success': False,
                        'error': '"message" is required and must be non-empty'}), 400
    if len(message) > Config.MAX_MESSAGE_LEN:
        return jsonify({'success': False,
                        'error': '"message" exceeds {} characters'.format(
                            Config.MAX_MESSAGE_LEN)}), 400

    try:
        bot_response = eval_runner.simulate_chatbot_response(message)
        evaluation   = eval_runner.evaluator.evaluate_response(message, bot_response)
        logger.info("Chat: compliance=%s empathy=%s",
                    evaluation.get('compliance_score'), evaluation.get('empathy_score'))
        return jsonify({'success': True,
                        'response': bot_response,
                        'evaluation': evaluation})
    except Exception as exc:
        logger.exception("Chat error")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── Dataset ───────────────────────────────────────────────────────────

@app.route('/api/generate-dataset', methods=['GET'])
@require_api_key
def generate_dataset():
    """Generate a synthetic adversarial evaluation dataset."""
    raw = request.args.get('count', '50')
    if not raw.isdigit() or int(raw) < 1:
        return jsonify({'success': False,
                        'error': '"count" must be a positive integer'}), 400

    count = min(int(raw), Config.MAX_DATASET_COUNT)
    try:
        questions = dataset_gen.generate_adversarial_questions(count)
        dataset_gen.save_dataset(questions)
        return jsonify({'success': True, 'count': len(questions), 'questions': questions})
    except Exception as exc:
        logger.exception("Dataset generation error")
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── Async evaluation ──────────────────────────────────────────────────

def _run_eval_with_save(dataset):
    # type: (List[dict]) -> dict
    """Worker: runs eval suite + saves results. Runs in background thread."""
    result = eval_runner.run_evaluation_suite(dataset)
    eval_runner.save_results(result)
    return result


@app.route('/api/run-eval', methods=['POST'])
@require_api_key
def run_evaluation():
    """Submit eval job → 202 + job_id. Poll /api/jobs/<id> for progress."""
    data = request.get_json(silent=True)

    if data and 'dataset' in data:
        dataset = data['dataset']
        if not isinstance(dataset, list) or not dataset:
            return jsonify({'success': False,
                            'error': '"dataset" must be a non-empty list'}), 400
    else:
        dataset = dataset_gen.load_dataset()
        if not dataset:
            return jsonify({
                'success': False,
                'error': 'No dataset found. Call GET /api/generate-dataset first.',
            }), 400

    if len(dataset) > Config.MAX_DATASET_COUNT:
        dataset = dataset[:Config.MAX_DATASET_COUNT]

    # Validate every item has a non-empty 'question' string
    invalid = [i for i, d in enumerate(dataset)
               if not isinstance(d, dict) or not str(d.get('question', '')).strip()]
    if invalid:
        return jsonify({
            'success': False,
            'error': '{} dataset item(s) are missing a "question" field (indices: {})'.format(
                len(invalid), invalid[:5]),
        }), 400

    job_id = queue.submit(_run_eval_with_save, dataset,
                          dataset_size=len(dataset))
    logger.info("Eval job %s submitted (%d items)", job_id, len(dataset))

    return jsonify({
        'success':  True,
        'job_id':   job_id,
        'status':   JobState.PENDING.value,
        'message':  'Evaluation started. Poll /api/jobs/{} for progress.'.format(job_id),
        'poll_url': '/api/jobs/{}'.format(job_id),
    }), 202


# ── Job management ────────────────────────────────────────────────────

@app.route('/api/jobs/<job_id>', methods=['GET'])
@require_api_key
def get_job_status(job_id):
    status = queue.get_status(job_id)
    if status is None:
        return jsonify({'success': False,
                        'error': 'Job {} not found'.format(job_id)}), 404
    return jsonify({'success': True, 'job': status})


@app.route('/api/jobs/<job_id>/result', methods=['GET'])
@require_api_key
def get_job_result(job_id):
    status = queue.get_status(job_id)
    if status is None:
        return jsonify({'success': False,
                        'error': 'Job {} not found'.format(job_id)}), 404
    if status['state'] != JobState.DONE.value:
        return jsonify({
            'success': False,
            'error':   'Job not done yet (state={})'.format(status['state']),
            'job':     status,
        }), 409
    return jsonify({'success': True, 'results': queue.get_result(job_id)})


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
@require_api_key
def cancel_job(job_id):
    if queue.get_status(job_id) is None:
        return jsonify({'success': False,
                        'error': 'Job {} not found'.format(job_id)}), 404
    return jsonify({'success': True, 'cancelled': queue.cancel(job_id)})


@app.route('/api/jobs', methods=['GET'])
@require_api_key
def list_jobs():
    return jsonify({'success': True, 'jobs': queue.list_jobs(limit=50)})


# ── Results / Dashboard ───────────────────────────────────────────────

@app.route('/api/results', methods=['GET'])
@require_api_key
def get_results():
    try:
        return jsonify({'success': True, 'data': eval_runner.load_results()})
    except Exception as exc:
        logger.exception("Results load error")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/dashboard-data', methods=['GET'])
@require_api_key
def get_dashboard_data():
    try:
        all_results = eval_runner.load_results()
        if not all_results.get('evaluations'):
            return jsonify({
                'success': True,
                'data': {'latest_metrics': None, 'drift_data': [],
                         'message': 'No evaluations yet'},
            })

        latest     = all_results['evaluations'][-1]
        drift_data = eval_runner.get_drift_data()

        return jsonify({
            'success': True,
            'data': {
                'latest_metrics':    latest.get('metrics'),
                'latest_timestamp':  latest.get('timestamp'),
                'provider':          latest.get('provider', Config.LLM_PROVIDER),
                'model':             latest.get('model',    Config.MODEL_NAME),
                'drift_data':        drift_data,
                'total_evaluations': len(all_results['evaluations']),
            },
        })
    except Exception as exc:
        logger.exception("Dashboard error")
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/mock-drift-data', methods=['GET'])
def get_mock_drift_data():
    """Synthetic 30-day drift data for demo. No auth required."""
    base = datetime.now(timezone.utc)
    data = [
        {
            'timestamp':       (base - timedelta(days=29 - i)).isoformat(),
            'compliance_rate': round(max(0.6, 0.95 - i*0.01 + random.uniform(-0.05, 0.05)), 3),
            'avg_empathy':     round(4.0 + random.uniform(-0.3, 0.3), 2),
            'total_flags':     random.randint(0, 5),
        }
        for i in range(30)
    ]
    return jsonify({'success': True, 'data': data})


# ═════════════════════════════════════════════════════════════════════
# Entry point (dev only — Render uses gunicorn via Procfile)
# ═════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Sentinel Compliance Monitor API v2.0  (dev server)")
    logger.info("URL:      http://localhost:%s", os.getenv('PORT', '5000'))
    logger.info("Provider: %s  (%s)", Config.LLM_PROVIDER, Config.MODEL_NAME)
    logger.info("Auth:     %s", 'ENABLED' if Config.EVAL_API_KEY else 'DISABLED')
    logger.info("=" * 60)

    app.run(
        debug=os.getenv('FLASK_DEBUG', '0') == '1',
        host='0.0.0.0',
        port=int(os.getenv('PORT', '5000')),
    )