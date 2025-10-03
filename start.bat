@echo off
title AI Newspaper Servers

echo Starting AI Newspaper...
echo.

REM Start Backend in a minimized window with a unique title
echo Starting Backend (FastAPI on port 8000)...
start "AI-Backend" /MIN cmd /c "cd backend && uvicorn backendServer:app --reload"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start Frontend in a minimized window with a unique title
echo Starting Frontend (Express on port 3000)...
start "AI-Frontend" /MIN cmd /c "cd frontend && npm run dev"

echo.
echo ================================================
echo Both servers are running!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo ================================================
echo.
echo IMPORTANT: Close this window to stop ALL servers
echo Press any key to stop all servers and exit...
pause >nul

REM Cleanup - Kill the named windows
echo.
echo Stopping servers...
taskkill /FI "WINDOWTITLE eq AI-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AI-Frontend*" /F >nul 2>&1
echo Servers stopped.
timeout /t 1 /nobreak >nul
