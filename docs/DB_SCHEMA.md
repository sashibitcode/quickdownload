# QuickDownload - Storage Model & In-Memory Data Structures

## 1. Overview
QuickDownload operates a stateless, high-throughput media pipeline designed to eliminate relational database bottlenecks. All transient operational state is managed through synchronized in-memory dictionaries, thread coordination events, and managed ephemeral disk storage.

---

## 2. In-Memory Data Structures

### 2.1 Metadata Cache Schema (`METADATA_CACHE`)
Stores extracted media attributes and format lists to avoid redundant network calls to upstream platforms.

- **Data Structure**: `dict[str, tuple[dict[str, Any], float]]`
- **Key**: Canonical Media URL (`str`)
- **Value**: Tuple of `(info_dict, timestamp)`
- **TTL**: 1800 seconds (30 minutes)

```typescript
interface CachedMetadata {
  id: string;                      // Upstream Video ID (e.g. "dQw4w9WgXcQ")
  title: string;                   // Media Title
  duration: number;                // Duration in seconds
  thumbnail: string;               // High-res preview image URL
  uploader: string;                // Channel or account username
  channel_url?: string;            // Upstream profile URL
  view_count?: number;             // View statistics
  formats: MediaFormat[];          // Available stream profiles
  cached_at: number;               // UNIX timestamp (seconds)
}

interface MediaFormat {
  format_id: string;               // e.g. "137" (1080p video) or "140" (128k audio)
  ext: string;                     // "mp4", "m4a", "webm"
  resolution?: string;             // "1920x1080"
  height?: number;                 // Vertical pixel count
  width?: number;                  // Horizontal pixel count
  filesize?: number;               // Exact byte size if known
  filesize_approx?: number;        // Approximate byte size for DASH manifests
  vcodec: string;                  // e.g. "avc1.640028" or "none" (audio-only)
  acodec: string;                  // e.g. "mp4a.40.2" or "none" (video-only)
  url: string;                     // Direct upstream CDN chunk URL
}
```

---

### 2.2 Active Download Coordination Table (`ACTIVE_DOWNLOAD_EVENTS`)
Tracks currently executing background downloads to prevent race conditions and duplicate download threads for the same media item.

- **Data Structure**: `dict[str, threading.Event]`
- **Synchronization**: Protected by `ACTIVE_DOWNLOAD_LOCK = threading.Lock()`
- **Key**: Target filename or video ID (`str`)
- **Value**: Standard library `threading.Event` instance

```
+---------------------------------------------+--------------------+
| Key (Filename / Video ID)                   | Event State        |
+---------------------------------------------+--------------------+
| "video_dQw4w9WgXcQ_720p.mp4"                | Event (set / wait) |
| "dQw4w9WgXcQ"                               | Event (alias)      |
+---------------------------------------------+--------------------+
```

---

### 2.3 Filename Alias Table (`FILE_NAME_ALIASES`)
Maps sanitized user-facing download filenames to internal disk paths.

- **Data Structure**: `dict[str, str]`
- **Key**: Requested URL-encoded filename
- **Value**: Actual on-disk path inside `DOWNLOAD_DIR`

---

## 3. Ephemeral Filesystem Storage Schema

All packaged media binaries reside temporarily on the host volume inside `DOWNLOAD_DIR` (defaults to OS temporary directory `/tmp/quickdownload-downloads`).

### 3.1 Directory Organization
```
$DOWNLOAD_DIR/
├── [title]-[id].mp4         # Fully packaged video ready for download
├── [title]-[id].mp3         # Extracted and tagged MP3 audio file
├── [id].f137.mp4.part       # Transient video-only fragment stream
└── [id].f140.m4a.part       # Transient audio-only fragment stream
```

### 3.2 File Retention & Purge Lifecycle (TTL Rules)
- **Max Age**: 1800 seconds (30 minutes). Files older than 30 minutes are deleted.
- **Corrupt / Incomplete Files**: Any dangling `.part`, `.ytdl`, or `.temp` files are automatically deleted upon each new download trigger.
- **Error Cleanup**: If an upstream extraction fails midway, `cleanup_failed_artifacts()` unlinks all partial fragments for that specific video ID to preserve disk space.
