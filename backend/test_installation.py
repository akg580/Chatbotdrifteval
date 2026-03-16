#!/usr/bin/env python3
"""
test_installation.py

Validates the Compliance Monitor installation for whichever LLM provider
is configured in .env (groq / anthropic / openai).
Run from the backend/ directory:  python3 test_installation.py
"""

import sys
import os


# ---------------------------------------------------------------------------

def test_python_version():
    print("Testing Python version...")
    v = sys.version_info
    if v.major >= 3 and v.minor >= 8:
        print(f"  PASS  Python {v.major}.{v.minor}.{v.micro}")
        return True
    print(f"  FAIL  Python {v.major}.{v.minor}.{v.micro} — need 3.8+")
    return False


def test_core_imports():
    print("\nTesting core package imports...")
    core = {
        'flask':       'Flask',
        'flask_cors':  'Flask-CORS',
        'dotenv':      'python-dotenv',
        'requests':    'requests',
    }
    ok = True
    for pkg, label in core.items():
        try:
            __import__(pkg)
            print(f"  PASS  {label}")
        except ImportError:
            print(f"  FAIL  {label} — run: pip install {pkg}")
            ok = False
    return ok


def test_provider_import():
    """Check that the SDK for the configured provider is installed."""
    print("\nTesting LLM provider SDK...")
    from dotenv import load_dotenv
    load_dotenv()

    provider = os.getenv('LLM_PROVIDER', 'groq').lower()
    sdk_map  = {
        'groq':      ('groq',      'groq'),
        'anthropic': ('anthropic', 'anthropic'),
        'openai':    ('openai',    'openai'),
    }

    if provider not in sdk_map:
        print(f"  FAIL  Unknown LLM_PROVIDER={provider!r}")
        return False

    module, install_name = sdk_map[provider]
    try:
        __import__(module)
        print(f"  PASS  {module} SDK (provider={provider})")
        return True
    except ImportError:
        print(f"  FAIL  {module} not installed — run: pip install {install_name}")
        return False


def test_file_structure():
    print("\nTesting file structure...")
    required = [
        'app.py',
        'config.py',
        'requirements.txt',
        'models/evaluator.py',
        'services/dataset_generator.py',
        'services/eval_runner.py',
        'data/eval_results.json',
        'data/synthetic_dataset.json',
    ]
    ok = True
    for path in required:
        if os.path.exists(path):
            print(f"  PASS  {path}")
        else:
            print(f"  MISS  {path} — not found (may be auto-created on first run)")
            # data/ files missing is a warning, not a hard failure
            if not path.startswith('data/'):
                ok = False
    return ok


def test_env_config():
    """Check that the active provider's API key is configured."""
    print("\nTesting environment configuration...")
    from dotenv import load_dotenv
    load_dotenv()

    if not os.path.exists('.env'):
        print("  FAIL  .env file not found — run: cp .env.example .env")
        return False
    print("  PASS  .env file found")

    provider = os.getenv('LLM_PROVIDER', 'groq').lower()
    key_map  = {
        'groq':      'GROQ_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'openai':    'OPENAI_API_KEY',
    }
    env_name = key_map.get(provider, 'GROQ_API_KEY')
    value    = os.getenv(env_name, '')

    if value and value not in ('your_api_key_here', 'your_groq_key_here',
                                'your_anthropic_key_here', 'your_openai_key_here'):
        print(f"  PASS  {env_name} configured (provider={provider})")
        return True
    else:
        print(f"  WARN  {env_name} is not set or still a placeholder")
        print(f"        Edit .env and add your {provider} API key")
        return False


def test_syntax():
    print("\nTesting Python syntax...")
    files = [
        'app.py',
        'config.py',
        'models/evaluator.py',
        'services/dataset_generator.py',
        'services/eval_runner.py',
    ]
    ok = True
    for path in files:
        try:
            with open(path) as f:
                compile(f.read(), path, 'exec')
            print(f"  PASS  {path}")
        except FileNotFoundError:
            print(f"  SKIP  {path} — not found")
        except SyntaxError as exc:
            print(f"  FAIL  {path} — {exc}")
            ok = False
    return ok


# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  COMPLIANCE MONITOR — INSTALLATION TEST")
    print("=" * 60)

    tests = [
        ("Python version",       test_python_version),
        ("Core imports",         test_core_imports),
        ("Provider SDK",         test_provider_import),
        ("File structure",       test_file_structure),
        ("Environment config",   test_env_config),
        ("Python syntax",        test_syntax),
    ]

    results = []
    for name, fn in tests:
        try:
            results.append((name, fn()))
        except Exception as exc:
            print(f"  ERROR  {name}: {exc}")
            results.append((name, False))

    passed = sum(1 for _, r in results if r)
    total  = len(results)

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for name, r in results:
        print(f"  {'PASS' if r else 'FAIL'}  {name}")

    print()
    if passed == total:
        print("  All tests passed — ready to run!")
        print()
        print("  Next steps:")
        print("    1.  python3 app.py")
        print("    2.  Open frontend/index.html")
        print("    3.  Click Generate Dataset, then Run Evaluation")
        return 0
    else:
        print(f"  {total - passed} test(s) failed — see messages above.")
        print("  See QUICKSTART.md for help.")
        return 1


if __name__ == '__main__':
    sys.exit(main())