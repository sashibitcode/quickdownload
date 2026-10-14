# QuickDownload - Deployment & Infrastructure Guide

## 1. Production Architecture Overview
QuickDownload uses a split-deployment model:
1. **Frontend**: Deployed to **Vercel** as a globally cached Single Page Application (SPA).
2. **Backend**: Deployed to **Render** (or Docker on any Linux host/VPS) as an asynchronous Python container with FFmpeg binaries installed.

---

## 2. Environment Variables Specification

### 2.1 Backend Environment Configuration
Configure these variables in your Render / Server environment:

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `PORT` | Yes (Render provides) | `8000` | Network port for Uvicorn ASGI server. |
| `FRONTEND_ORIGINS` | Recommended | `http://127.0.0.1:5173` | Comma-separated list of allowed frontend domains for CORS. |
| `PUBLIC_API_URL` | Recommended | `""` | Public HTTPS URL of the backend (e.g. `https://quickdownload-api.onrender.com`). |
| `DOWNLOAD_DIR` | No | `/tmp/quickdownload-downloads` | Host directory for temporary video storage and FFmpeg merging. |
| `YT_PROXY` | Optional | `""` | HTTP/HTTPS proxy URL or Webshare format (`host:port:user:pass`) for IP rotation. |
| `YT_COOKIES` | Optional | `""` | Base64-encoded Netscape-format cookies to bypass YouTube SABR/age-restrictions. |
| `INSTAGRAM_COOKIES_B64` | Optional | `""` | Base64-encoded cookies for Instagram private/login-gated reels. |

---

## 3. Render Backend Deployment

The repository includes a root `render.yaml` specification for zero-config one-click deployment:

```yaml
services:
  - type: web
    name: quickdownload-api
    env: python
    region: oregon
    plan: starter
    buildCommand: |
      pip install -U pip setuptools wheel
      pip install -r backend/requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.12.0
      - key: FRONTEND_ORIGINS
        value: https://quick-d.vercel.app,http://localhost:5173
```

### 3.1 Docker Alternative (`backend/Dockerfile`)
For self-hosting on Railway, Fly.io, or VPS:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 4. Vercel Frontend Deployment

The frontend connects to the backend through the Vite build environment and Vercel edge rewrite rules.

### 4.1 `vercel.json` Configuration
```json
{
  "buildCommand": "vite build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

### 4.2 Frontend Environment Variable (`.env.production`)
Set in Vercel Project Settings:
```env
VITE_API_URL=https://quickdownload-api.onrender.com
```

---

## 5. Health Monitoring & Maintenance
- **Health Check URL**: `GET /health` returns JSON status and FFmpeg binary resolution.
- **Auto-Sleep Prevention**: Set up an external heartbeat pinger (e.g., UptimeRobot) targeting `/health` every 10 minutes to prevent Render free-tier instances from spinning down.
- **Disk Hygiene**: `cleanup_downloads()` runs continuously to ensure temporary downloads do not exceed host disk allocations.
