#!/bin/bash

# RSS Backend Startup Script
# This script starts the RSS backend server on port 8001

echo "Starting AI Newspaper RSS Backend Server..."
echo "Server will be available at: http://localhost:8001"
echo "RSS Feed: http://localhost:8001/rss"
echo ""

# Change to backend directory
cd backend

# Activate virtual environment and start server
source venv/bin/activate

# Start the RSS backend server with auto-reload
echo "Starting RSS backend with nodemon-like auto-reload..."
uvicorn rss_backend:app --reload --host 0.0.0.0 --port 8001
