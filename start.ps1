# AI Newspaper PowerShell Launcher
$Host.UI.RawUI.WindowTitle = "AI Newspaper Servers"

Write-Host "Starting AI Newspaper..." -ForegroundColor Cyan
Write-Host ""

# Start Backend
Write-Host "Starting Backend (FastAPI on port 8000)..." -ForegroundColor Yellow
Set-Location backend
$backendProcess = Start-Process -FilePath "uvicorn" -ArgumentList "backendServer:app", "--reload" -PassThru -WindowStyle Minimized
Set-Location ..

# Wait for backend to initialize
Start-Sleep -Seconds 3

# Start Frontend
Write-Host "Starting Frontend (Express on port 3000)..." -ForegroundColor Yellow
Set-Location frontend
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -WindowStyle Minimized
Set-Location ..

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "Both servers are running!" -ForegroundColor Green
Write-Host "Backend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C or close this window to stop all servers..." -ForegroundColor Yellow
Write-Host ""

# Cleanup function
$cleanup = {
    Write-Host ""
    Write-Host "Stopping servers..." -ForegroundColor Red
    
    # Kill backend process and its children
    if ($backendProcess -and !$backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Kill frontend process and its children
    if ($frontendProcess -and !$frontendProcess.HasExited) {
        Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Also kill any remaining uvicorn and node processes
    Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process node -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -like "*AI*"} | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Write-Host "Servers stopped." -ForegroundColor Green
    Start-Sleep -Seconds 1
}

# Register cleanup on exit
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanup | Out-Null

# Trap Ctrl+C
try {
    # Wait indefinitely
    while ($true) {
        Start-Sleep -Seconds 1
        
        # Check if processes are still running
        if ($backendProcess.HasExited -and $frontendProcess.HasExited) {
            Write-Host "Both servers have stopped." -ForegroundColor Red
            break
        }
    }
}
finally {
    # Run cleanup
    & $cleanup
}

