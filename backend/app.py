from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
import json

from services.dataset_generator import DatasetGenerator
from services.eval_runner import EvalRunner
from config import Config

app = Flask(__name__)
CORS(app)

# Initialize services
dataset_gen = DatasetGenerator()
eval_runner = EvalRunner()

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

@app.route('/')
def home():
    """API home endpoint"""
    return jsonify({
        'message': 'Compliance Monitor API',
        'version': '1.0',
        'endpoints': {
            'generate_dataset': '/api/generate-dataset',
            'run_eval': '/api/run-eval',
            'results': '/api/results',
            'dashboard': '/api/dashboard-data'
        }
    })

@app.route('/api/generate-dataset', methods=['GET'])
def generate_dataset():
    """Generate synthetic adversarial dataset"""
    try:
        count = int(request.args.get('count', 50))
        
        print(f"Generating {count} adversarial questions...")
        questions = dataset_gen.generate_adversarial_questions(count)
        
        # Save dataset
        filepath = dataset_gen.save_dataset(questions)
        
        return jsonify({
            'success': True,
            'count': len(questions),
            'filepath': filepath,
            'questions': questions
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/run-eval', methods=['POST'])
def run_evaluation():
    """Run evaluation suite"""
    try:
        # Get dataset (from request or load saved)
        data = request.get_json()
        
        if data and 'dataset' in data:
            dataset = data['dataset']
        else:
            # Load saved dataset
            dataset = dataset_gen.load_dataset()
            
            if not dataset:
                return jsonify({
                    'success': False,
                    'error': 'No dataset found. Generate dataset first.'
                }), 400
        
        # Run evaluation
        print("Running evaluation suite...")
        eval_results = eval_runner.run_evaluation_suite(dataset)
        
        # Save results
        eval_runner.save_results(eval_results)
        
        return jsonify({
            'success': True,
            'results': eval_results
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get all evaluation results"""
    try:
        results = eval_runner.load_results()
        return jsonify({
            'success': True,
            'data': results
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dashboard-data', methods=['GET'])
def get_dashboard_data():
    """Get aggregated dashboard data"""
    try:
        # Get latest results
        all_results = eval_runner.load_results()
        
        if not all_results.get('evaluations'):
            return jsonify({
                'success': True,
                'data': {
                    'latest_metrics': None,
                    'drift_data': [],
                    'message': 'No evaluations run yet'
                }
            })
        
        # Latest metrics
        latest = all_results['evaluations'][-1]
        
        # Drift data
        drift_data = eval_runner.get_drift_data()
        
        return jsonify({
            'success': True,
            'data': {
                'latest_metrics': latest['metrics'],
                'latest_timestamp': latest['timestamp'],
                'drift_data': drift_data,
                'total_evaluations': len(all_results['evaluations'])
            }
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/mock-drift-data', methods=['GET'])
def get_mock_drift_data():
    """Generate mock drift data for demo purposes"""
    import random
    from datetime import timedelta
    
    mock_data = []
    base_date = datetime.now()
    
    for i in range(30):
        date = base_date - timedelta(days=29-i)
        
        # Simulate drift (compliance starts high, drifts down)
        compliance = max(0.6, 0.95 - (i * 0.01) + random.uniform(-0.05, 0.05))
        empathy = 4.0 + random.uniform(-0.3, 0.3)
        flags = random.randint(0, 5)
        
        mock_data.append({
            'timestamp': date.isoformat(),
            'compliance_rate': round(compliance, 3),
            'avg_empathy': round(empathy, 2),
            'total_flags': flags
        })
    
    return jsonify({
        'success': True,
        'data': mock_data
    })

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Compliance Monitor API Starting...")
    print("=" * 50)
    print(f"📍 Server: http://localhost:5000")
    print(f"📊 Dashboard: Open frontend/index.html")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
