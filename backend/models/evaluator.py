from config import Config
import json

# Import LLM client from dataset_generator
import sys
sys.path.append('..')
from services.dataset_generator import LLMClient

class LLMEvaluator:
    """LLM-as-a-Judge evaluator for chatbot responses"""
    
    def __init__(self):
        self.client = LLMClient()
        self.policies = Config.BANK_POLICIES
    
    def evaluate_response(self, question, bot_response):
        """Evaluate a single chatbot response for compliance and empathy"""
        
        policies_text = "\n".join([f"- {k}: {v}" for k, v in self.policies.items()])
        
        prompt = f"""You are an expert evaluator for banking chatbot responses. Evaluate the following interaction:

CUSTOMER QUESTION: {question}

BOT RESPONSE: {bot_response}

BANK POLICIES:
{policies_text}

Evaluate the response on two dimensions:

1. EMPATHY (1-5 scale):
   - 1: Cold, dismissive, rude
   - 2: Minimal empathy, mechanical
   - 3: Adequate empathy, professional
   - 4: Good empathy, warm and understanding
   - 5: Excellent empathy, deeply understanding and supportive

2. POLICY COMPLIANCE (0 or 1):
   - 0: Violates policies (makes unauthorized promises, gives incorrect info)
   - 1: Complies with policies (follows all guidelines, appropriate escalation)

Return ONLY a JSON object with this exact structure:
{{
  "empathy_score": <1-5>,
  "compliance_score": <0 or 1>,
  "empathy_reasoning": "brief explanation",
  "compliance_reasoning": "brief explanation",
  "flags": ["any concerning phrases or promises"],
  "overall_assessment": "brief summary"
}}"""

        try:
            content = self.client.generate(prompt, max_tokens=1000, temperature=0.3)
            
            # Extract JSON
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()
            
            evaluation = json.loads(json_str)
            
            return evaluation
            
        except Exception as e:
            print(f"Error evaluating response: {e}")
            return {
                "empathy_score": 3,
                "compliance_score": 1,
                "empathy_reasoning": "Error in evaluation",
                "compliance_reasoning": "Error in evaluation",
                "flags": [],
                "overall_assessment": f"Evaluation failed: {str(e)}"
            }
    
    def batch_evaluate(self, qa_pairs):
        """Evaluate multiple Q&A pairs"""
        results = []
        
        for i, pair in enumerate(qa_pairs):
            print(f"Evaluating {i+1}/{len(qa_pairs)}...")
            
            evaluation = self.evaluate_response(
                pair['question'],
                pair['bot_response']
            )
            
            results.append({
                "id": pair.get('id', i),
                "question": pair['question'],
                "bot_response": pair['bot_response'],
                "evaluation": evaluation,
                "timestamp": pair.get('timestamp', None)
            })
        
        return results
