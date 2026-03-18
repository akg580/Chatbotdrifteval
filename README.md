# Compliance Monitor for Customer Support Chatbot
url: https://sentinelchatbot.netlify.app/
##   Run with Groq API (OPTIONS FOR OTHER TOO)

An AI-powered evaluation system that monitors chatbot responses for policy compliance and empathy. supports FREE Groq API

## Overview

### The Problem
Banks use chatbots for customer service, but fear they might make unauthorized promises (like "Yes, we'll waive your fee") that violate policies.

### The Solution
Automated evaluation suite that runs nightly to test chatbot safety using:
-  **Synthetic Dataset**: Generates 50 adversarial questions
-  **LLM-as-a-Judge**: Dual scoring (Compliance + Empathy)
- **Drift Dashboard**: Monitors compliance over time

##  Features
-  Synthetic adversarial dataset generation
-  LLM-as-a-Judge evaluation system
- Drift detection dashboard
- Compliance scoring (0-1 scale)
- Empathy scoring (1-5 scale)
- **100% FREE with Groq API**

##  Cost Options

### Option 1: Groq (FREE - Recommended!)
-  100% FREE forever
-  No credit card required
- Fast inference (3x faster!)
- Great quality (Llama 3.3 70B)
-  **See GROQ_FREE_SETUP.md**

### Option 2: Anthropic Claude (Paid)
- Best quality for nuanced evaluation
- ~$0.50 per 50 evaluations
- Requires API key

### Option 3: OpenAI GPT-4 (Paid)
- Good alternative
- ~$0.30 per 50 evaluations
- Requires API key

## Quick Start (FREE with Groq)

### 1. Get FREE Groq API Key
```bash
# Visit: https://console.groq.com/
# Sign up (just email, no credit card!)
# Create API key
```

### 2. Backend Setup
```bash
cd backend
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add:
# LLM_PROVIDER=groq
# GROQ_API_KEY=your_key_here
```

### 3. Run Server
```bash
python app.py
```

### 4. Open Dashboard
Open `frontend/index.html` in your browser

## Architecture
- **Backend**: Flask API with multi-provider LLM support
- **Frontend**: Vanilla JavaScript dashboard
- **Evaluation**: LLM-as-a-Judge pattern
- **Storage**: JSON files (can be replaced with database)

## API Endpoints
- `GET /api/generate-dataset` - Generate synthetic adversarial questions
- `POST /api/run-eval` - Run evaluation on chatbot responses
- `GET /api/results` - Get evaluation results and drift data
- `GET /api/dashboard-data` - Get aggregated dashboard metrics

## Tech Stack
- Python 3.8+
- Flask
- Groq / Anthropic / OpenAI (configurable)
- Chart.js for visualizations

## Documentation
- **GROQ_FREE_SETUP.md** - Complete FREE setup guide 
- **QUICKSTART.md** - Fast 5-minute setup
- **SETUP_GUIDE.md** - Detailed instructions
- **PROJECT_OVERVIEW.md** - Full project details
- **CODE_REFERENCE.md** - All code in one place

## Switching Providers

Just edit `.env` file:

```bash
# For Groq (FREE):
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key

# For Anthropic:
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key

# For OpenAI:
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key
```


