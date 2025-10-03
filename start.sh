#!/bin/bash

echo "Starting AI Newspaper..."
echo ""

# Start backend in background
echo "Starting Backend (FastAPI on port 8000)..."
cd backend && uvicorn backendServer:app --reload &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start frontend in background
echo "Starting Frontend (Express on port 3000)..."
cd ../frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "Both servers are running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers..."

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait

