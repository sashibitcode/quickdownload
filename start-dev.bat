@echo off
title QuickDownload Dev Server
echo ===================================================
echo Starting QuickDownload Full-Stack Environment
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173 (proxied to :8000)
echo ===================================================

start "QuickDownload Backend" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
start "QuickDownload Frontend" cmd /k "cd /d %~dp0 && npm run dev"

echo Services launched in separate terminals!
