@echo off
title QuickDownload Live Tunnel Server
echo ===================================================
echo Starting QuickDownload with Cloudflare Live Tunnel
echo Local Backend:  http://localhost:8000
echo Local Frontend: http://localhost:5180
echo ===================================================

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] .venv not found. Creating virtualenv...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r backend\requirements.txt
)

echo Starting Backend Server on port 8000...
start "QuickDownload Backend" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting Cloudflare Tunnel...
echo Look for the public https://xxxx.trycloudflare.com URL below:
start "Cloudflare Live Tunnel" cmd /k "cd /d %~dp0 && cloudflared.exe tunnel --url http://localhost:8000"

echo ===================================================
echo Done! Your backend is now publicly accessible via Cloudflare Tunnel.
echo Copy the https://xxxx.trycloudflare.com URL from the tunnel window
echo and paste it into your Vercel Environment Variables (VITE_API_URL).
echo ===================================================
pause
