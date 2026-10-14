# QuickDownload - Edge Cases, Failovers & Error Recovery

## 1. Overview
Media extraction pipelines must handle high volatility due to platform API changes, anti-scraping challenges, copyright restrictions, and network edge cases. QuickDownload incorporates defensive engineering strategies across both YouTube and Instagram extraction engines.

---

## 2. YouTube Extraction Edge Cases

### 2.1 YouTube SABR & "Sign in to confirm you're not a bot" (HTTP 429)
- **Symptom**: YouTube rejects datacenter IP addresses with bot verification challenges or SABR player errors.
- **Failover Strategy**:
  1. **Multi-Client Emulation Cascade**:
     `yt-dlp` rotates from the primary desktop client (`WEB`) to mobile and embedded clients (`IOS`, `ANDROID`, `MWEB`, `TV_EMBEDDED`). Mobile clients frequently bypass desktop bot challenges.
  2. **Proxy Tunneling**:
     When `YT_PROXY` is configured, outgoing stream requests are routed through residential rotating proxies.
  3. **Ephemeral Cookie Authentication**:
     If `YT_COOKIES` is configured, session tokens validate the request as an authenticated browser session.

### 2.2 Age-Restricted & Members-Only Videos
- **Symptom**: Content requires age confirmation or channel membership.
- **Handling**:
  - The API catches `DownloadError` and returns a structured `400 Bad Request` with an explicit diagnostic message:
    `"This YouTube video is age-restricted and requires account authentication."` or `"This YouTube video requires channel membership or purchase."`
  - Prevents server-side crash loops or unhandled `500 Internal Server Errors`.

### 2.3 Separate DASH Streams for 1080p / 4K (Video-Only + Audio-Only)
- **Symptom**: YouTube does not provide combined MP4 streams above 720p. 1080p video has no audio track by default.
- **Handling**:
  - The backend requests the highest video stream (`bestvideo[height<=1080][ext=mp4]`) and highest audio stream (`bestaudio[ext=m4a]`).
  - Merges both using FFmpeg stream copying:
    ```bash
    ffmpeg -i video.mp4 -i audio.m4a -c copy -movflags +faststart output.mp4
    ```
  - Result: Instantaneous multiplexing without lossy re-encoding or heavy CPU spikes.

---

## 3. Instagram Extraction Edge Cases

### 3.1 Private Accounts & Expired Reels
- **Symptom**: User attempts to download content from a private Instagram profile or an expired 24-hour story.
- **Handling**:
  - Validates response payloads. If Instagram returns an empty media array or login redirect, the API cleanly returns:
    `"This Instagram content is private or requires login. Only publicly accessible Instagram Reel/Post links can be downloaded."`

### 3.2 Dynamic Carousel Posts (Multi-Slide Media)
- **Symptom**: User submits a link containing multiple images and videos in a single carousel.
- **Handling**:
  - Filters the carousel elements to prioritize the primary video slide, preventing format mismatch crashes.

---

## 4. System & Server-Level Edge Cases

### 4.1 Server Disk Full / Temp Volume Exhaustion
- **Risk**: Repeated video downloads fill the host disk, crashing the server.
- **Prevention Strategy**:
  - `cleanup_downloads()` executes on every incoming request, identifying files older than 30 minutes (`1800s`).
  - Dangling temporary fragments (`.part`, `.ytdl`, `.temp`) from cancelled or aborted client requests are immediately removed.

### 4.2 Gateway Timeout on Slow Client Connections
- **Risk**: Client internet connection is slow; cloud proxy (Render/Cloudflare) kills the connection after 30 seconds.
- **Prevention Strategy**:
  - QuickDownload finishes server packaging first, stores the finished file, and provides a direct static file download link.
  - The client can resume or download at their own network speed with `Accept-Ranges: bytes` support.

### 4.3 FFmpeg Binary Missing on Host Environment
- **Symptom**: Host machine does not have FFmpeg installed in system `PATH`.
- **Handling**:
  - QuickDownload's `setup_ffmpeg()` scans multiple fallback locations:
    1. System `PATH` (`ffmpeg` or `ffmpeg.exe`).
    2. Windows WinGet package directories (`%LOCALAPPDATA%\Microsoft\WinGet\Packages`).
    3. Bundled Python `imageio-ffmpeg` binary.
  - Automatically resolves and initializes the binary without requiring manual system environment configuration.
