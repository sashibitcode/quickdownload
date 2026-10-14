# QuickDownload - Technology Stack & Architecture Specifications

## 1. Executive Overview
QuickDownload is an industrial-grade, zero-transcode media extraction pipeline designed to deliver high-resolution MP4 video and MP3 audio streams from YouTube and Instagram in sub-second to low-latency timeframes. The platform is architected as a distributed client-server ecosystem with a Python FastAPI asynchronous core and a React 19 single-page application frontend.

---

## 2. Core Backend Technologies

### 2.1 Runtime & Server Engine
- **Language**: Python 3.12+ (CPython)
- **Web Framework**: FastAPI (`>= 0.115.0`)
  - Asynchronous ASGI architecture leveraging `uvloop` (Linux/Docker) and standard `asyncio` event loop.
  - High concurrency request dispatching with Starlette core abstractions.
  - Automatic OpenAPI / Swagger UI generation and Pydantic-powered request validation.
- **ASGI Server**: Uvicorn (`>= 0.30.0`)
  - Production worker management running behind reverse proxies (Render / Cloudflare).

### 2.2 Media Ingestion & Extraction Engine
- **Extractor**: `yt-dlp` (`>= 2026.8.19` / latest nightly)
  - Specialized video metadata extraction with multi-client token emulation (`WEB`, `IOS`, `ANDROID`, `MWEB`, `TV_EMBEDDED`).
  - Concurrent fragment downloading (`concurrent_fragment_downloads = 4`) with pre-allocated buffer sizes (`buffersize = 524288`).
  - Anti-bot signature deciphering and cookie authentication support.
- **Stream Transcoding & Packaging**: FFmpeg (via `imageio-ffmpeg` and native binary)
  - Zero-transcode multiplexing (`-c copy`) delivering instantaneous stream merging without CPU-intensive re-encoding.
  - Standalone binary resolution supporting cross-platform operating systems (Windows, Linux, macOS).
- **Transport & Fingerprint Emulation**: `curl-cffi`
  - High-precision browser TLS fingerprint imitation (JA3/JA4, HTTP/2 frame parameters) to circumvent edge CDN rate limits.

### 2.3 Data Validation & Serialization
- **Data Modeling**: Pydantic v2 (`>= 2.8.0`)
  - Strict input sanitization for video URLs, quality parameters, and output formats.

---

## 3. Frontend Technologies

### 3.1 Client Framework
- **Core Library**: React 19 (`^19.2.8`)
  - Concurrent rendering engine with automatic batching and transition hooks.
- **Build System & Dev Server**: Vite (`^8.3.0`)
  - Native ES module (ESM) serving during development with lightning-fast Hot Module Replacement (HMR).
  - Rollup-based production tree-shaking and minification.
- **Language**: TypeScript & ECMAScript 2024
  - Type-safe component definitions and interface contracts matching backend payloads.

### 3.2 Styling & Design System
- **CSS Architecture**: Vanilla CSS & Modern Responsive Design
  - Platform-adaptive ambient glow effects, responsive glassmorphism, dynamic progress indicators, and mobile-first touch optimization.
- **Linter & Static Analysis**: Oxlint (`^1.81.0`)
  - High-performance Rust-based static code analysis for strict JavaScript/TypeScript linting.

---

## 4. Infrastructure & Hosting

| Layer | Provider / Tool | Configuration |
| :--- | :--- | :--- |
| **Backend API** | Render / Docker | Python 3.12 container, automated health checks, dynamic port binding (`PORT`), temp volume storage |
| **Frontend UI** | Vercel | Global Edge Network, SPA client-side rewrite rules (`vercel.json`) |
| **Proxy Gateway** | Webshare / Rotating HTTP Proxies | Residential / datacenter HTTP proxy tunneling (`YT_PROXY`) |
| **Authentication** | Base64 Encrypted Netscape Cookies | Ephemeral in-memory cookie injection for private/age-restricted media bypass |

---

## 5. Dependency Matrix Summary

```
quickdownload/
├── backend/
│   ├── python (3.12+)
│   ├── fastapi (0.115.0+)
│   ├── uvicorn (0.30.0+)
│   ├── yt-dlp (2026.08.19+)
│   ├── imageio-ffmpeg
│   ├── curl-cffi
│   └── pydantic (2.8.0+)
└── frontend/
    ├── react (19.2.8+)
    ├── vite (8.3.0+)
    ├── oxlint (1.81.0+)
    └── @types/react (19.2.18+)
```
