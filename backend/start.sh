#!/bin/bash

# Compliance Monitor - Startup Script

echo "=================================================="
echo "🚀 Starting Compliance Monitor"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: Please run this script from the backend/ directory"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found"
    echo "Creating from template..."
    cp .env.example .env
    echo ""
    echo "❌ Please edit .env and add your Anthropic API key"
    echo "   Then run this script again"
    exit 1
fi

# Check if dependencies are installed
echo "🔍 Checking dependencies..."
python3 -c "import flask, anthropic" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Dependencies not installed"
    echo "Installing now..."
    pip3 install -r requirements.txt
fi

# Run the app
echo ""
echo "✅ Starting server..."
echo ""
python3 app.py
