import json
from datetime import datetime
from config import Config
from models.evaluator import LLMEvaluator
from services.dataset_generator import LLMClient

class EvalRunner:
    """Runs evaluation suite and manages results"""
    
    def __init__(self):
        self.evaluator = LLMEvaluator()
        self.client = LLMClient()
    
    def simulate_chatbot_response(self, question):
        """Simulate a chatbot response for testing (replace with actual bot API)"""
        
        prompt = f"""You are a customer service chatbot for a bank. Respond to this customer question professionally and helpfully:

CUSTOMER: {question}

Important guidelines:
- Be empathetic and understanding
- Follow bank policies (don't make unauthorized promises)
- Escalate when appropriate
- Be professional but warm

Provide ONLY the chatbot response, nothing else."""

        try:
            response_text = self.client.generate(prompt, max_tokens=500, temperature=0.7)
            return response_text.strip()
            
        except Exception as e:
            return f"I apologize, but I'm experiencing technical difficulties. Please contact our support team."
    
    def run_evaluation_suite(self, dataset):
        """Run full evaluation on dataset"""
        
        print(f"Running evaluation on {len(dataset)} questions...")
        
        # Generate bot responses
        qa_pairs = []
        for item in dataset:
            bot_response = self.simulate_chatbot_response(item['question'])
            qa_pairs.append({
                'id': item['id'],
                'question': item['question'],
                'bot_response': bot_response,
                'category': item.get('category', 'general'),
                'risk_level': item.get('risk_level', 'medium'),
                'timestamp': datetime.now().isoformat()
            })
        
        # Evaluate responses
        results = self.evaluator.batch_evaluate(qa_pairs)
        
        # Calculate aggregate metrics
        metrics = self._calculate_metrics(results)
        
        return {
            'results': results,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat(),
            'dataset_size': len(dataset)
        }
    
    def _calculate_metrics(self, results):
        """Calculate aggregate metrics from evaluation results"""
        
        if not results:
            return {}
        
        total = len(results)
        
        # Compliance metrics
        compliant_count = sum(1 for r in results if r['evaluation']['compliance_score'] == 1)
        compliance_rate = compliant_count / total
        
        # Empathy metrics
        empathy_scores = [r['evaluation']['empathy_score'] for r in results]
        avg_empathy = sum(empathy_scores) / total
        
        # Risk breakdown
        high_risk_compliant = sum(1 for r in results 
                                  if r.get('risk_level') == 'high' 
                                  and r['evaluation']['compliance_score'] == 1)
        high_risk_total = sum(1 for r in results if r.get('risk_level') == 'high')
        
        # Flags
        total_flags = sum(len(r['evaluation'].get('flags', [])) for r in results)
        
        return {
            'total_evaluations': total,
            'compliance_rate': round(compliance_rate, 3),
            'avg_empathy_score': round(avg_empathy, 2),
            'compliant_count': compliant_count,
            'non_compliant_count': total - compliant_count,
            'high_risk_compliance_rate': round(high_risk_compliant / high_risk_total, 3) if high_risk_total > 0 else 0,
            'total_flags': total_flags,
            'empathy_distribution': {
                '5_star': sum(1 for s in empathy_scores if s == 5),
                '4_star': sum(1 for s in empathy_scores if s == 4),
                '3_star': sum(1 for s in empathy_scores if s == 3),
                '2_star': sum(1 for s in empathy_scores if s == 2),
                '1_star': sum(1 for s in empathy_scores if s == 1)
            }
        }
    
    def save_results(self, eval_results, filepath=None):
        """Save evaluation results"""
        if filepath is None:
            filepath = Config.RESULTS_PATH
        
        # Load existing results
        try:
            with open(filepath, 'r') as f:
                all_results = json.load(f)
        except FileNotFoundError:
            all_results = {'evaluations': []}
        
        # Append new results
        all_results['evaluations'].append(eval_results)
        
        # Save
        with open(filepath, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        return filepath
    
    def load_results(self, filepath=None):
        """Load evaluation results"""
        if filepath is None:
            filepath = Config.RESULTS_PATH
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'evaluations': []}
    
    def get_drift_data(self):
        """Get time-series data for drift detection"""
        all_results = self.load_results()
        
        drift_data = []
        for eval_run in all_results.get('evaluations', []):
            drift_data.append({
                'timestamp': eval_run['timestamp'],
                'compliance_rate': eval_run['metrics']['compliance_rate'],
                'avg_empathy': eval_run['metrics']['avg_empathy_score'],
                'total_flags': eval_run['metrics']['total_flags']
            })
        
        return drift_data
