@echo off
title QuickDownload Dev Server
echo ===================================================
echo Starting QuickDownload Full-Stack Environment
echo Backend:  http://localhost:8000 (0.0.0.0:8000)
echo Frontend: http://localhost:5180 (0.0.0.0:5180, proxied to :8000)
echo Available locally and on your LAN WiFi for mobile testing!
echo ===================================================

start "QuickDownload Backend" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
start "QuickDownload Frontend" cmd /k "cd /d %~dp0 && npm run dev -- --host 0.0.0.0"

echo Services launched in separate terminals!
