#!/bin/bash
# AI Newspaper Backend Startup Script
# Starts the FastAPI backend server on all interfaces

cd "$(dirname "$0")/backend"

echo "========================================"
echo "🚀 Starting AI Newspaper Backend Server"
echo "========================================"
echo ""

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 8000 is already in use!"
    echo "   Stopping existing backend..."
    pkill -f "uvicorn backendServer"
    sleep 2
fi

# Start the backend server
echo "📡 Starting server on http://0.0.0.0:8000"
echo "   (accessible via localhost, 127.0.0.1, and your IP)"
echo ""

python3 -m uvicorn backendServer:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info

echo ""
echo "========================================"
echo "✅ Backend server stopped"
echo "========================================"

