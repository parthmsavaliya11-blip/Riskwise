@echo off
REM ====================================================================
REM  Risk Cockpit - one-click launcher
REM  Double-click this file to start the app. It opens two small windows
REM  (backend + frontend) and then your browser. Keep both windows open
REM  while you use the app; close them when you're done.
REM ====================================================================

cd /d "%~dp0"

echo Starting the backend (calculations, port 8000)...
start "Risk Cockpit - Backend"  cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo Starting the frontend (the website, port 5173)...
start "Risk Cockpit - Frontend" cmd /k "cd frontend && npm run dev"

echo Waiting a few seconds for the servers to wake up...
timeout /t 7 >nul

echo Opening the app in your browser...
start "" "http://localhost:5173"

echo.
echo ====================================================================
echo  Two windows are now open: "Backend" and "Frontend".
echo  Leave them open while you use Risk Cockpit.
echo  To stop the app later, just close those two windows.
echo  You can close THIS window now.
echo ====================================================================
echo.
pause
