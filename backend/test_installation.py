#!/usr/bin/env python3
"""
Test script to validate Compliance Monitor installation
Run this after setup to ensure everything is working
"""

import sys
import os

def test_python_version():
    """Test Python version"""
    print("🔍 Testing Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Need 3.8+")
        return False

def test_imports():
    """Test required package imports"""
    print("\n🔍 Testing package imports...")
    packages = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
        'anthropic': 'Anthropic SDK',
        'dotenv': 'Python-dotenv',
        'requests': 'Requests'
    }
    
    all_ok = True
    for package, name in packages.items():
        try:
            __import__(package)
            print(f"✅ {name} - Installed")
        except ImportError:
            print(f"❌ {name} - Missing")
            all_ok = False
    
    return all_ok

def test_file_structure():
    """Test file structure"""
    print("\n🔍 Testing file structure...")
    
    required_files = [
        'app.py',
        'config.py',
        'requirements.txt',
        'models/evaluator.py',
        'services/dataset_generator.py',
        'services/eval_runner.py',
        'data/eval_results.json',
        'data/synthetic_dataset.json'
    ]
    
    all_ok = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} - Found")
        else:
            print(f"❌ {file_path} - Missing")
            all_ok = False
    
    return all_ok

def test_env_file():
    """Test .env file"""
    print("\n🔍 Testing environment configuration...")
    
    if os.path.exists('.env'):
        print("✅ .env file - Found")
        
        # Check if API key is set
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('ANTHROPIC_API_KEY', '')
        if api_key and api_key != 'your_api_key_here':
            print("✅ ANTHROPIC_API_KEY - Configured")
            return True
        else:
            print("⚠️  ANTHROPIC_API_KEY - Not set or using placeholder")
            print("   Edit .env and add your actual API key")
            return False
    else:
        print("❌ .env file - Not found")
        print("   Run: cp .env.example .env")
        print("   Then add your Anthropic API key")
        return False

def test_syntax():
    """Test Python syntax"""
    print("\n🔍 Testing Python syntax...")
    
    files_to_test = [
        'app.py',
        'config.py',
        'models/evaluator.py',
        'services/dataset_generator.py',
        'services/eval_runner.py'
    ]
    
    all_ok = True
    for file_path in files_to_test:
        try:
            with open(file_path, 'r') as f:
                compile(f.read(), file_path, 'exec')
            print(f"✅ {file_path} - Valid syntax")
        except SyntaxError as e:
            print(f"❌ {file_path} - Syntax error: {e}")
            all_ok = False
    
    return all_ok

def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 COMPLIANCE MONITOR - INSTALLATION TEST")
    print("=" * 60)
    
    tests = [
        ("Python Version", test_python_version),
        ("Package Imports", test_imports),
        ("File Structure", test_file_structure),
        ("Environment Config", test_env_file),
        ("Python Syntax", test_syntax)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error running {name}: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("\n" + "=" * 60)
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\n✅ Your installation is ready!")
        print("\n🚀 Next steps:")
        print("   1. Run: python3 app.py")
        print("   2. Open: frontend/index.html")
        print("   3. Click 'Generate Dataset' in the dashboard")
        return 0
    else:
        print(f"⚠️  {total - passed} TEST(S) FAILED")
        print("=" * 60)
        print("\n❌ Please fix the issues above before running the app")
        print("\n📖 See QUICKSTART.md for help")
        return 1

if __name__ == '__main__':
    exit(main())
