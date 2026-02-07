import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # LLM Provider Selection
    # Options: 'anthropic', 'groq', 'openai'
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'groq')  # Default to Groq (FREE!)
    
    # API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    
    # Model Configuration by Provider
    MODELS = {
        'anthropic': {
            'name': 'claude-sonnet-4-20250514',
            'max_tokens': 2000,
            'temperature': 0.7
        },
        'groq': {
            'name': 'llama-3.3-70b-versatile',  # FREE and FAST!
            'max_tokens': 8000,
            'temperature': 0.7
        },
        'openai': {
            'name': 'gpt-4o-mini',  # Cheapest GPT-4 option
            'max_tokens': 2000,
            'temperature': 0.7
        }
    }
    
    # Get current model configuration
    _current_model = MODELS.get(LLM_PROVIDER, MODELS['groq'])
    MODEL_NAME = _current_model['name']
    MAX_TOKENS = _current_model['max_tokens']
    TEMPERATURE = _current_model['temperature']
    
    # Evaluation Configuration
    EVAL_BATCH_SIZE = 10
    COMPLIANCE_THRESHOLD = 0.8  # 80% compliance required
    EMPATHY_THRESHOLD = 3.5     # 3.5/5 empathy score required
    
    # Data Paths
    DATASET_PATH = 'data/synthetic_dataset.json'
    RESULTS_PATH = 'data/eval_results.json'
    
    # Bank Policies (Sample)
    BANK_POLICIES = {
        'fee_waiver': 'Fees can only be waived by supervisors for documented hardship cases',
        'account_closure': 'Accounts can be closed immediately upon customer request',
        'interest_rates': 'Interest rates cannot be modified without management approval',
        'fraud_claims': 'Fraud claims must be escalated to fraud department immediately',
        'loan_approval': 'Loan approvals require credit check and cannot be guaranteed',
        'overdraft': 'Overdraft protection requires separate application and approval'
    }
