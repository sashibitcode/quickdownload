# QuickDownload - AI Discoverability & LLM Integration Frameworks

## 1. Overview & Purpose
This document establishes the protocols, machine-readable manifests, and metadata structures enabling autonomous AI agents, LLMs, and developer tooling to understand, index, and interface programmatically with the QuickDownload media processing engine.

---

## 2. Machine-Readable Interface Metadata

### 2.1 OpenAPI / Swagger Specification
QuickDownload automatically serves dynamic, compliant OpenAPI 3.1.0 specifications at:
- **Interactive UI**: `http://127.0.0.1:8000/docs`
- **ReDoc Alternative**: `http://127.0.0.1:8000/redoc`
- **JSON Schema**: `http://127.0.0.1:8000/openapi.json`

Autonomous AI agents can directly fetch and parse `/openapi.json` to formulate valid function calls and tool definitions.

---

## 3. Function Calling & Tool Definition Contract

For AI agents implementing Model Context Protocol (MCP) or OpenAI / Anthropic Function Calling:

```json
{
  "name": "extract_media_stream",
  "description": "Extract downloadable video or audio streams from YouTube or Instagram URLs with resolution selection.",
  "parameters": {
    "type": "object",
    "properties": {
      "url": {
        "type": "string",
        "description": "The full YouTube or Instagram media URL (e.g., https://www.youtube.com/watch?v=... or https://www.instagram.com/reel/...)"
      },
      "platform": {
        "type": "string",
        "enum": ["youtube", "instagram"],
        "description": "Target media platform"
      },
      "quality": {
        "type": "string",
        "enum": ["1080p", "720p", "360p", "mp3"],
        "default": "720p",
        "description": "Desired output quality format"
      }
    },
    "required": ["url", "platform"]
  }
}
```

---

## 4. Semantic Search & Discoverability Tags

```json
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "QuickDownload",
  "applicationCategory": "MultimediaApplication",
  "operatingSystem": "All",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "featureList": [
    "YouTube Video Download",
    "YouTube Shorts Extraction",
    "Instagram Reels Download",
    "Lossless Zero-Transcode Stream Multiplexing",
    "MP4 1080p Full HD",
    "High-Bitrate MP3 Audio Extraction"
  ],
  "creator": {
    "@type": "Person",
    "name": "Shashikant Raj",
    "url": "https://sashibitcode.vercel.app"
  }
}
```

---

## 5. Security & Input Sanitization for LLMs
- **URL Whitelisting**: Strict regex verification guarantees that only legitimate `youtube.com`, `youtu.be`, and `instagram.com` domains are processed.
- **SSRF Prevention**: All local IP addresses (`127.0.0.1`, `10.x.x.x`, `192.168.x.x`, `169.254.x.x`) and loopback interfaces are blocked from proxy redirection.
- **Header Injection Defense**: Filenames are sanitized via strict ASCII filtering and URL encoding before being passed to `Content-Disposition`.
