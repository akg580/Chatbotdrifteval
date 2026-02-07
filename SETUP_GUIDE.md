# 🚀 Setup Guide - Compliance Monitor

## Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Anthropic API key ([Get one here](https://console.anthropic.com/))

## Step-by-Step Setup

### 1. Backend Setup

#### Navigate to backend directory
```bash
cd compliance-monitor/backend
```

#### Create virtual environment (recommended)
```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

#### Install dependencies
```bash
pip install -r requirements.txt
```

#### Configure API key
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Anthropic API key
# On macOS/Linux
nano .env

# On Windows
notepad .env
```

Add your API key:
```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

#### Run the backend server
```bash
python app.py
```

You should see:
```
==================================================
🚀 Compliance Monitor API Starting...
==================================================
📍 Server: http://localhost:5000
📊 Dashboard: Open frontend/index.html
==================================================
```

### 2. Frontend Setup

#### Open the dashboard
Simply open `frontend/index.html` in your browser:
- **Option 1**: Double-click `index.html`
- **Option 2**: Drag `index.html` into your browser
- **Option 3**: Use a local server (recommended for development)

#### Using a local server (optional but recommended)
```bash
# Navigate to frontend directory
cd compliance-monitor/frontend

# Python 3
python -m http.server 8000

# Then open: http://localhost:8000
```

## 🎯 Using the Application

### 1. Generate Synthetic Dataset
- Click **"📝 Generate Dataset"** button
- Wait for Claude to generate 50 adversarial questions
- View the questions in the "Synthetic Dataset" section

### 2. Run Evaluation
- After generating the dataset, click **"▶️ Run Evaluation"**
- The system will:
  - Simulate chatbot responses to each question
  - Evaluate each response using LLM-as-a-Judge
  - Score compliance (0/1) and empathy (1-5)
- View results in the dashboard

### 3. Monitor Drift
- The charts show compliance and empathy trends over time
- Each evaluation run adds a new data point
- Watch for degradation in metrics

## 📊 Understanding the Dashboard

### Metrics
- **Compliance Rate**: % of responses that follow bank policies
- **Avg Empathy Score**: Average empathy rating (out of 5)
- **Total Flags**: Number of policy violations detected
- **Evaluations Run**: Total number of test questions evaluated

### Charts
- **Compliance Drift**: Shows policy adherence over time
- **Empathy Trend**: Tracks customer experience quality

### Results
- Each result shows:
  - Original customer question
  - Chatbot response
  - Compliance score (✅/❌)
  - Empathy score (1-5)
  - Detailed analysis
  - Any flags or concerns

## 🔧 Troubleshooting

### "Failed to connect to API" error
- Make sure the backend server is running (`python app.py`)
- Check that it's on port 5000
- Verify CORS is enabled

### "Invalid API key" error
- Check your `.env` file
- Ensure your API key is valid
- Restart the backend server after changing `.env`

### No data showing
- First generate a dataset
- Then run evaluation
- Check browser console for errors (F12)

### Slow evaluation
- Each evaluation requires API calls to Claude
- 50 questions may take 5-10 minutes
- Be patient and don't refresh the page

## 🎨 Customization

### Modify Bank Policies
Edit `backend/config.py`:
```python
BANK_POLICIES = {
    'your_policy': 'Your policy description',
    # Add more policies
}
```

### Change Dataset Size
```bash
# In browser console or modify API call
fetch('http://localhost:5000/api/generate-dataset?count=100')
```

### Adjust Evaluation Criteria
Edit `backend/models/evaluator.py` to modify:
- Empathy scoring rubric
- Compliance criteria
- Evaluation prompt

## 📝 API Endpoints

- `GET /api/generate-dataset?count=50` - Generate dataset
- `POST /api/run-eval` - Run evaluation
- `GET /api/results` - Get all results
- `GET /api/dashboard-data` - Get dashboard metrics
- `GET /api/mock-drift-data` - Get mock data for demo

## 🚨 Important Notes

1. **API Costs**: Each evaluation makes multiple API calls to Claude
2. **Data Persistence**: Results are stored in JSON files
3. **Mock Data**: The system can show mock drift data for demos
4. **Simulated Bot**: Currently uses Claude to simulate bot responses

## 🎓 For Your Portfolio

When showcasing this project:

1. **The Problem**: Banks need to ensure chatbots don't make unauthorized promises
2. **Your Solution**: Automated evaluation suite with LLM-as-a-Judge
3. **Key Features**:
   - Synthetic adversarial dataset generation
   - Dual-metric evaluation (compliance + empathy)
   - Drift detection dashboard
   - Scalable evaluation pipeline

4. **Technical Highlights**:
   - LLM-as-a-Judge pattern
   - Prompt engineering for evaluation
   - Full-stack implementation
   - Real-time monitoring

## 📚 Next Steps

Potential enhancements:
- [ ] Database integration (PostgreSQL/MongoDB)
- [ ] Email alerts for drift detection
- [ ] A/B testing different prompts
- [ ] Integration with actual chatbot APIs
- [ ] Historical trend analysis
- [ ] Export reports to PDF
- [ ] User authentication
- [ ] Scheduled nightly runs

Good luck! 🎉
