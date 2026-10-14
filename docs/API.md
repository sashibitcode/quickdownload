# QuickDownload - API Specification & Endpoint Documentation

## 1. Overview
The QuickDownload backend provides high-performance RESTful API endpoints for media extraction, format inspection, background packaging, and binary streaming. All endpoints support cross-origin requests (CORS) with origin validation and structured JSON error responses.

**Base URLs**:
- Local Development: `http://127.0.0.1:8000`
- Production API: Configurable via `PUBLIC_API_URL` (e.g., `https://quickdownload-backend.onrender.com`)

---

## 2. API Endpoints

### 2.1 Health Check & Server Status
Check the health, uptime, and availability of the extraction engine.

- **Endpoint**: `GET /health` or `GET /api/health`
- **Authentication**: None
- **Response**: `200 OK`

```json
{
  "status": "healthy",
  "service": "QuickDownload Media Pipeline",
  "timestamp": 1728905400.12,
  "ffmpeg_available": true
}
```

---

### 2.2 YouTube Media Extraction & Packaging
Inspect, resolve direct CDN streams, or trigger background zero-transcode MP4/MP3 packaging for YouTube videos and Shorts.

- **Endpoint**: `POST /download-youtube` (or `POST /api/download-youtube`)
- **Headers**:
  - `Content-Type: application/json`
  - `Accept: application/json`

#### Request Body
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "quality": "720p"
}
```

| Field | Type | Required | Default | Description |
| :--- | :--- | :---: | :---: | :--- |
| `url` | `string` | **Yes** | — | Valid YouTube watch link, short link (`youtu.be`), or YouTube Shorts link (`/shorts/`). |
| `quality` | `string` | No | `"720p"` | Target output resolution (`"1080p"`, `"720p"`, `"360p"`, `"mp3"`). |

#### Response (`200 OK`)
```json
{
  "success": true,
  "status": "ready",
  "message": "YouTube video is ready to download.",
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "platform": "YouTube",
  "media_badge": "YouTube Video",
  "quality": "720p",
  "qualities": [
    {
      "id": "1080p",
      "label": "MP4 1080p",
      "quality": "1080p",
      "ext": "mp4",
      "type": "video",
      "badge": "Full HD",
      "filesize": 78643200
    },
    {
      "id": "720p",
      "label": "MP4 720p",
      "quality": "720p",
      "ext": "mp4",
      "type": "video",
      "badge": "HD • Recommended",
      "filesize": 41943040,
      "is_default": true
    },
    {
      "id": "360p",
      "label": "MP4 360p",
      "quality": "360p",
      "ext": "mp4",
      "type": "video",
      "badge": "Data Saver",
      "filesize": 15728640
    },
    {
      "id": "mp3",
      "label": "MP3 Audio",
      "quality": "mp3",
      "ext": "mp3",
      "type": "audio",
      "badge": "Audio",
      "filesize": 4194304
    }
  ],
  "file_name": "Rick_Astley_Never_Gonna_Give_You_Up-dQw4w9WgXcQ.mp4",
  "download_url": "https://api.quickdownload.app/download-file?filename=Rick_Astley_Never_Gonna_Give_You_Up-dQw4w9WgXcQ.mp4",
  "direct_url": "https://rr3---sn-4g5ednkk.googlevideo.com/videoplayback?...",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "duration": 213,
  "uploader": "Rick Astley",
  "filesize": 41943040
}
```

---

### 2.3 Instagram Reel / Video Media Extraction
Extract lossless MP4 video from Instagram Reels, Video posts, and carousel video items.

- **Endpoint**: `POST /download-instagram` (or `POST /api/download-instagram`)
- **Headers**:
  - `Content-Type: application/json`

#### Request Body
```json
{
  "url": "https://www.instagram.com/reel/C_example_id/",
  "quality": "720p"
}
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "status": "ready",
  "message": "Instagram video is ready to download.",
  "title": "instagram-video-C_example_id",
  "url": "https://www.instagram.com/reel/C_example_id/",
  "platform": "Instagram",
  "media_badge": "Instagram Reel",
  "quality": "720p",
  "qualities": [
    {
      "id": "720p",
      "label": "MP4 HD",
      "quality": "720p",
      "ext": "mp4",
      "type": "video",
      "badge": "Original HD",
      "filesize": 18456200,
      "is_default": true
    },
    {
      "id": "mp3",
      "label": "MP3 Audio",
      "quality": "mp3",
      "ext": "mp3",
      "type": "audio",
      "badge": "Audio",
      "filesize": null
    }
  ],
  "file_name": "instagram-video-C_example_id.mp4",
  "download_url": "https://api.quickdownload.app/download-file?filename=instagram-video-C_example_id.mp4",
  "thumbnail": "https://scontent.cdninstagram.com/v/...",
  "duration": 45,
  "uploader": "creator_account",
  "filesize": 18456200
}
```

---

### 2.4 Binary Media File Streaming & Download
Streams the packaged media binary directly to the client with `Content-Disposition: attachment` headers, prompting the user's browser download dialog.

- **Endpoint**: `GET /download-file?filename={encoded_filename}`
- **Query Parameters**:
  - `filename`: URL-encoded basename of the file in the server download cache.
- **Response Headers**:
  - `Content-Type: video/mp4` (or `audio/mpeg`)
  - `Content-Disposition: attachment; filename="Rick_Astley.mp4"`
  - `Content-Length: 41943040`
  - `Accept-Ranges: bytes`

---

## 3. Standard Error Contract

All error responses strictly follow the standardized JSON schema:

```json
{
  "success": false,
  "error": "Human-readable error description explaining the issue.",
  "detail": "Detailed internal diagnostics or platform limitation note."
}
```

### Common HTTP Status Codes
| Code | Error Condition | Remediation |
| :---: | :--- | :--- |
| `400` | Invalid URL or platform restriction (e.g., private media, age-restricted, removed). | Prompt user to verify the URL or ensure the media is publicly accessible. |
| `422` | Request validation error (missing `url` or malformed payload). | Validate request JSON matches schema before dispatch. |
| `429` | Platform rate limit reached (e.g., YouTube SABR challenge or Instagram throttle). | Retry with proxy rotation or wait a cooldown period. |
| `500` | Stream extraction or FFmpeg packaging failure. | Server automatic fallback or report unexpected format. |
