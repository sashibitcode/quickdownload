import base64
import json
import mimetypes
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from typing import Any, cast
import urllib.error
from urllib.parse import quote, urlparse
import urllib.request

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from imageio_ffmpeg import get_ffmpeg_exe
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
import yt_dlp  # type: ignore[import-untyped]

# Environment variables
# Environment variables (supports ALLOWED_ORIGINS, FRONTEND_ORIGINS, and FRONTEND_ORIGIN)
raw_origins = (
    os.getenv("ALLOWED_ORIGINS")
    or os.getenv("FRONTEND_ORIGINS")
    or os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
)
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in raw_origins.split(",")
    if origin.strip()
]

PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "").strip().rstrip("/")
DEBUG_TOKEN = os.getenv("DEBUG_TOKEN", "").strip()
YOUTUBE_COOKIES_B64 = (os.getenv("YT_COOKIES") or os.getenv("YOUTUBE_COOKIES_B64", "")).strip()
INSTAGRAM_COOKIES_B64 = os.getenv("INSTAGRAM_COOKIES_B64", "").strip()
YOUTUBE_COOKIES_FILE = (os.getenv("YOUTUBE_COOKIES_FILE") or os.getenv("YT_COOKIES_FILE") or os.getenv("COOKIES_FILE", "")).strip()
LOCAL_YT_COOKIES = os.path.join(os.path.dirname(__file__), "cookies.txt")
if not YOUTUBE_COOKIES_FILE and os.path.isfile(LOCAL_YT_COOKIES):
    YOUTUBE_COOKIES_FILE = LOCAL_YT_COOKIES
INSTAGRAM_COOKIES_FILE = (os.getenv("INSTAGRAM_COOKIES_FILE") or os.getenv("IG_COOKIES_FILE", "")).strip()
YT_PO_TOKEN = os.getenv("YT_PO_TOKEN", "").strip()
YT_VISITOR_DATA = os.getenv("YT_VISITOR_DATA", "").strip()


def normalize_proxy_url(raw_proxy: str | None) -> str:
    """Normalize user-provided proxy strings (including Webshare export formats) into standard URLs."""
    if not raw_proxy:
        return ""
    p = raw_proxy.strip().strip("'\"")
    if not p:
        return ""
    if "://" in p:
        return p
    # Handle Webshare colon export format: host:port:username:password
    parts = p.split(":")
    if len(parts) == 4:
        host, port, user, pwd = parts
        return f"http://{user}:{pwd}@{host}:{port}"
    if "@" in p:
        return f"http://{p}"
    return f"http://{p}"


YOUTUBE_PROXY = normalize_proxy_url(
    os.getenv("YT_PROXY") or os.getenv("YOUTUBE_PROXY") or os.getenv("HTTP_PROXY", "")
)
DOWNLOAD_DIR = os.getenv(
    "DOWNLOAD_DIR",
    os.path.join(tempfile.gettempdir(), "quickdownload-downloads"),
)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Active background downloads coordinator and metadata cache for fast latency
ACTIVE_DOWNLOAD_EVENTS: dict[str, threading.Event] = {}
ACTIVE_DOWNLOAD_LOCK = threading.Lock()
METADATA_CACHE: dict[str, tuple[dict[str, Any], float]] = {}
FILE_NAME_ALIASES: dict[str, str] = {}
CACHE_TTL_SECONDS = 1800  # 30 minutes cache



def resolve_executable(name: str):
    if shutil.which(name):
        return shutil.which(name)
    if shutil.which(name + ".exe"):
        return shutil.which(name + ".exe")
    root = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(root):
        for dirpath, _, filenames in os.walk(root):
            if name in filenames or (name + ".exe") in filenames:
                candidate = os.path.join(dirpath, name if name in filenames else name + ".exe")
                if os.path.isfile(candidate):
                    return candidate
    return None


def setup_ffmpeg():
    # 1. System FFmpeg
    sys_ffmpeg = resolve_executable("ffmpeg") or resolve_executable("ffmpeg.exe")
    if sys_ffmpeg and os.path.isfile(sys_ffmpeg):
        return sys_ffmpeg, os.path.dirname(sys_ffmpeg)

    # 2. imageio-ffmpeg
    try:
        raw_ffmpeg = get_ffmpeg_exe()
        if raw_ffmpeg and os.path.isfile(raw_ffmpeg):
            bin_dir = os.path.dirname(raw_ffmpeg)
            standard_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            target_exe = os.path.join(bin_dir, standard_name)
            if not os.path.isfile(target_exe):
                try:
                    shutil.copyfile(raw_ffmpeg, target_exe)
                except Exception as e:
                    print("Could not copy ffmpeg to standard name:", e)
            if os.path.isfile(target_exe):
                return target_exe, bin_dir
            return raw_ffmpeg, bin_dir
    except Exception as e:
        print("imageio_ffmpeg setup error:", repr(e))

    return None, None


FFMPEG_PATH, FFMPEG_DIR = setup_ffmpeg()
FFPROBE_PATH = resolve_executable("ffprobe.exe") or resolve_executable("ffprobe")
DENO_PATH = resolve_executable("deno.exe") or resolve_executable("deno")
NODE_PATH = resolve_executable("node.exe") or resolve_executable("node")

if FFMPEG_DIR:
    os.environ["PATH"] = f"{FFMPEG_DIR}{os.pathsep}{os.environ.get('PATH', '')}"
if DENO_PATH:
    os.environ["PATH"] = f"{os.path.dirname(DENO_PATH)}{os.pathsep}{os.environ.get('PATH', '')}"
if NODE_PATH:
    os.environ["PATH"] = f"{os.path.dirname(NODE_PATH)}{os.pathsep}{os.environ.get('PATH', '')}"
if FFMPEG_PATH:
    os.environ["FFMPEG_PATH"] = FFMPEG_PATH
if FFPROBE_PATH:
    os.environ["FFPROBE_PATH"] = FFPROBE_PATH
if NODE_PATH:
    os.environ["NODE_PATH"] = NODE_PATH


def get_js_runtimes_config():
    config = {}
    deno = DENO_PATH or resolve_executable("deno")
    node = NODE_PATH or resolve_executable("node")
    if deno:
        config["deno"] = {"path": deno}
    if node:
        config["node"] = {"path": node}
    return config if config else None

app = FastAPI(
    title="Quick Download API",
    description="Backend API for Quick Download multi-platform downloader",
    version="1.0.0",
)

# CORS configuration: Allow local ports, Vercel deployments, Render consoles, and custom domains
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:5180",
    "http://127.0.0.1:5180",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    *FRONTEND_ORIGINS,
]
# Clean out empty strings
allowed_origins = [o for o in allowed_origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+)(:\d+)?|https://([a-zA-Z0-9_-]+\.)?(vercel\.app|onrender\.com))$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length", "X-Filename"],
)


# Structured Error Handlers (Step 4 & 8)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        detail = exc.detail.get("detail") or exc.detail.get("error") or "Error processing request."
        code = exc.detail.get("code") or "HTTP_ERROR"
    else:
        detail = str(exc.detail) if exc.detail else "Error processing request."
        code = "HTTP_ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": detail,
            "detail": detail,
            "code": code,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msg = "; ".join(f"{err.get('loc', ['field'])[-1]}: {err.get('msg', 'invalid')}" for err in exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": f"Invalid request data: {error_msg}",
            "detail": f"Invalid request data: {error_msg}",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    print("UNHANDLED SERVER ERROR:", repr(exc))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Server returned an unexpected error. Please try again later.",
            "detail": str(exc),
        },
    )


def get_public_base_url(request: Request) -> str:
    """Return the HTTPS public base URL, ensuring Render reverse proxies are properly handled."""
    if PUBLIC_API_URL:
        return PUBLIC_API_URL

    forwarded_proto = None
    forwarded_host = None
    host = "127.0.0.1:8000"
    scheme = "http"

    if hasattr(request, "headers") and request.headers is not None:
        forwarded_proto = request.headers.get("x-forwarded-proto")
        forwarded_host = request.headers.get("x-forwarded-host")
        host = forwarded_host or request.headers.get("host") or "127.0.0.1:8000"

    try:
        scheme = forwarded_proto or (request.url.scheme if hasattr(request, "url") and hasattr(request.url, "scheme") else "http")
    except Exception:
        scheme = forwarded_proto or "http"

    if "onrender.com" in host or forwarded_proto == "https":
        scheme = "https"

    return f"{scheme}://{host}"


def cleanup_downloads(max_age_seconds: int = 1800):
    """Remove temporary files older than 30 minutes to prevent disk exhaustion."""
    now = time.time()
    try:
        if not os.path.exists(DOWNLOAD_DIR):
            return
        for entry in os.scandir(DOWNLOAD_DIR):
            if entry.is_file():
                try:
                    if now - entry.stat().st_mtime > max_age_seconds or entry.name.endswith((".part", ".ytdl", ".temp")):
                        os.remove(entry.path)
                except Exception:
                    pass
    except Exception:
        pass


def cleanup_failed_artifacts(identifier: str | None = None):
    """Remove partial or temporary files left behind when a download fails."""
    try:
        if not os.path.exists(DOWNLOAD_DIR):
            return
        for entry in os.scandir(DOWNLOAD_DIR):
            if entry.is_file():
                try:
                    if entry.name.endswith((".part", ".ytdl", ".temp")):
                        os.remove(entry.path)
                    elif identifier and len(identifier) > 3 and identifier in entry.name:
                        os.remove(entry.path)
                except Exception:
                    pass
    except Exception:
        pass


def create_cookie_file_from_env(cookie_data: str, prefix: str):
    """Write raw or base64-encoded Netscape cookies to a temp file, or return existing file path."""
    if not cookie_data:
        return None
    try:
        data_stripped = cookie_data.strip().strip("'\"")
        if not data_stripped:
            return None

        # Direct file path support (e.g. Render Secret File mounted at /etc/secrets/... or local file)
        if os.path.isfile(data_stripped):
            return data_stripped

        decoded: bytes | None = None

        # 1. Check if raw Netscape format was passed directly (contains tabs or # Netscape)
        if "\t" in data_stripped or "# Netscape" in data_stripped:
            decoded = data_stripped.encode("utf-8")

        # 2. Otherwise try base64 decoding (auto-stripping whitespace and auto-adding missing padding)
        if not decoded:
            try:
                clean_b64 = "".join(data_stripped.split())
                pad = (-len(clean_b64) % 4) * "="
                candidate = base64.b64decode(clean_b64 + pad)
                if b"\t" in candidate or b"# Netscape" in candidate or b".youtube.com" in candidate or b".instagram.com" in candidate:
                    decoded = candidate
            except Exception as b64_err:
                print(f"[Cookie Parse Error] Base64 decode failed for {prefix}:", repr(b64_err))

        # 3. If still not valid Netscape cookie bytes, DO NOT write an invalid cookie file!
        if not decoded or (b"\t" not in decoded and b"# Netscape" not in decoded):
            print(f"[Cookie Warning] Provided cookie data for {prefix} is not a valid Netscape format; omitting cookiefile to prevent yt-dlp crash.")
            return None

        temp_file = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".txt", delete=False)
        temp_file.write(decoded)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"Error decoding cookie file for {prefix}:", repr(e))
        return None


def find_downloaded_file(info: dict | None = None, title: str | None = None):
    valid_ext = {".mp4", ".webm", ".mkv", ".avi", ".flv", ".m4v", ".mov", ".mp3", ".m4a"}

    if info:
        req_dl = info.get("requested_downloads")
        if req_dl and isinstance(req_dl, list) and len(req_dl) > 0:
            filepath = req_dl[0].get("filepath")
            if filepath and os.path.isfile(filepath):
                return filepath

    candidates = []
    if os.path.exists(DOWNLOAD_DIR):
        for entry in os.scandir(DOWNLOAD_DIR):
            if not entry.is_file() or entry.name.endswith(".part"):
                continue

            name = entry.name.lower()
            ext = os.path.splitext(name)[1]
            if ext not in valid_ext:
                continue

            if title is not None:
                title_lower = title.lower()
                clean_title = "".join(ch for ch in title_lower if ch.isalnum() or ch in " -_.")
                clean_name = "".join(ch for ch in name if ch.isalnum() or ch in " -_.")
                if title_lower in name or (clean_title and clean_title in clean_name):
                    candidates.append(entry.path)
            else:
                candidates.append(entry.path)

    if candidates:
        return max(candidates, key=os.path.getmtime)

    # Fallback: most recent valid file in directory
    all_files = [
        entry.path for entry in os.scandir(DOWNLOAD_DIR)
        if entry.is_file() and not entry.name.endswith(".part") and os.path.splitext(entry.name.lower())[1] in valid_ext
    ]
    return max(all_files, key=os.path.getmtime) if all_files else None


def sanitize_youtube_url(url: str) -> str:
    """Normalize YouTube URL (including Shorts and youtu.be) and remove playlist/tracking parameters."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean
    try:
        parsed = urlparse(clean)
        netloc = (parsed.netloc or "").lower()
        path = parsed.path or ""

        # 1. Normalize youtu.be/<id> -> youtube.com/watch?v=<id>
        if "youtu.be" in netloc:
            video_id = path.strip("/").split("/")[0].split("?")[0]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"

        # 2. Normalize youtube.com/shorts/<id> -> youtube.com/watch?v=<id>
        if "youtube.com" in netloc and "/shorts/" in path:
            parts = path.split("/shorts/")
            if len(parts) > 1:
                video_id = parts[1].strip("/").split("/")[0].split("?")[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"

        # 3. If standard watch URL, preserve only the 'v' parameter
        if "youtube.com" in netloc and path == "/watch":
            from urllib.parse import parse_qs, urlencode
            qs = parse_qs(parsed.query)
            if "v" in qs and qs["v"]:
                clean_query = urlencode({"v": qs["v"][0]})
                return f"https://www.youtube.com/watch?{clean_query}"
    except Exception:
        pass
    return clean


def is_valid_youtube_url(url: str) -> bool:
    if not url:
        return False
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean
    try:
        parsed = urlparse(clean)
        host = (parsed.netloc or "").lower()
        if not parsed.scheme or not parsed.netloc:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        allowed_hosts = {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be",
        }
        if not (host in allowed_hosts or host.endswith(".youtube.com")):
            return False
        if not parsed.path or parsed.path == "/":
            return False
        return True
    except Exception:
        return False


def is_valid_instagram_url(url: str) -> bool:
    if not url:
        return False
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean
    try:
        parsed = urlparse(clean)
        host = (parsed.netloc or "").lower()
        if not parsed.scheme or not parsed.netloc:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        allowed_hosts = {
            "instagram.com",
            "www.instagram.com",
            "m.instagram.com",
            "instagr.am",
            "www.instagr.am",
            "ddinstagram.com",
        }
        if host not in allowed_hosts and not host.endswith(".instagram.com") and not host.endswith(".instagr.am"):
            return False
        path = parsed.path.lower()
        if not path or len(path) <= 1:
            return False
        return any(segment in path for segment in ["/reel/", "/reels/", "/p/", "/tv/", "/stories/", "/s/", "/share/"]) or len(path) > 3
    except Exception:
        return False


class DownloadRequest(BaseModel):
    platform: str = ""
    url: str
    quality: str = "720p"
    format_type: str = "video"


# Root and Health check endpoints (available at / and /api)
@app.get("/")
@app.get("/api")
def home():
    return {
        "success": True,
        "message": "Quick Download API is running!",
        "status": "success",
    }


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "success": True,
        "status": "healthy",
    }


@app.get("/version")
@app.get("/api/version")
def version():
    proxy_info: dict[str, Any] = {"configured": bool(YOUTUBE_PROXY)}
    if YOUTUBE_PROXY:
        try:
            parsed = urlparse(YOUTUBE_PROXY)
            proxy_info["scheme"] = parsed.scheme
            proxy_info["host"] = parsed.hostname
            proxy_info["port"] = parsed.port
            proxy_info["has_auth"] = bool(parsed.username)
            if parsed.username:
                proxy_info["user_preview"] = parsed.username[:4] + "***"
            # Quick 6-second connectivity test to verify proxy connection to YouTube
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": YOUTUBE_PROXY, "https": YOUTUBE_PROXY})
            )
            req = urllib.request.Request("https://www.youtube.com/generate_204", headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=6) as resp:
                proxy_info["connectivity"] = f"connected ({resp.status})"
        except Exception as e:
            proxy_info["connectivity"] = f"failed: {str(e)}"
    else:
        proxy_info["connectivity"] = "none"

    return {
        "success": True,
        "version": "2.4.0",
        "proxy": proxy_info,
        "status": "active",
    }


def classify_youtube_error(exc: Exception) -> tuple[str, str]:
    """
    Classify yt-dlp extraction errors into granular machine-readable codes and user-friendly messages.
    Returns (code, message).
    Codes: BOT_BLOCKED, AGE_RESTRICTED, PRIVATE_OR_UNAVAILABLE, GEO_BLOCKED, TIMEOUT, FFMPEG_MISSING, EXTRACTOR_OUTDATED, UNKNOWN
    """
    err_str = str(exc).lower()

    # 1. Bot detection / Rate limiting
    if any(k in err_str for k in ["sign in to confirm you're not a bot", "bot", "automated queries", "429", "too many requests", "challenge"]):
        return (
            "BOT_BLOCKED",
            "YouTube blocked datacenter server requests (Bot detection / 429). Please configure YouTube cookies (YT_COOKIES) or proxy (YT_PROXY) on the server.",
        )

    # 2. Age-restricted
    if any(k in err_str for k in ["age", "inappropriate", "confirm your age"]):
        return (
            "AGE_RESTRICTED",
            "This YouTube video is age-restricted and requires account authentication via cookies.",
        )

    # 3. Private / unavailable / deleted
    if any(k in err_str for k in ["private", "unavailable", "removed", "does not exist", "not found", "deleted"]):
        return (
            "PRIVATE_OR_UNAVAILABLE",
            "This YouTube video is private, restricted, or unavailable.",
        )

    # 4. Geo-blocking
    if any(k in err_str for k in ["country", "geo", "region", "not available in your"]):
        return (
            "GEO_BLOCKED",
            "This YouTube video is geo-blocked and not available in the server's region.",
        )

    # 5. Timeouts
    if any(k in err_str for k in ["timeout", "timed out", "timedout"]):
        return (
            "TIMEOUT",
            "YouTube server request timed out. Please try again.",
        )

    # 6. Missing FFmpeg
    if any(k in err_str for k in ["ffmpeg", "ffprobe"]):
        return (
            "FFMPEG_MISSING",
            "FFmpeg is missing or failed on the server. Please verify FFmpeg installation.",
        )

    # 7. Outdated extractor / signature deciphering
    if any(k in err_str for k in ["signature deciphering", "unable to extract", "extractor", "ejs", "javascript runtime"]):
        return (
            "EXTRACTOR_OUTDATED",
            "YouTube player signature changed. Extractor or JS challenge solver requires update.",
        )

    # 8. Membership / Premium
    if any(k in err_str for k in ["members only", "premium", "purchase"]):
        return (
            "PRIVATE_OR_UNAVAILABLE",
            "This YouTube video requires channel membership or purchase.",
        )

    return (
        "UNKNOWN",
        f"Unable to process this YouTube video: {str(exc)[:150]}",
    )


def get_executable_version(cmd: list[str]) -> str | None:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        out = (res.stdout or res.stderr or "").strip()
        return out.split("\n")[0] if out else None
    except Exception as e:
        return f"error: {str(e)}"


@app.get("/debug/yt")
@app.get("/api/debug/yt")
def debug_yt(request: Request, token: str | None = None, url: str | None = None):
    # Verify token if DEBUG_TOKEN is set
    client_token = token or request.headers.get("x-debug-token") or ""
    if DEBUG_TOKEN and client_token != DEBUG_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid or missing debug token. Set ?token=... or X-Debug-Token header.",
        )

    yt_ver = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    ffmpeg_ver = get_executable_version([FFMPEG_PATH, "-version"]) if FFMPEG_PATH else None
    deno_path = DENO_PATH or resolve_executable("deno")
    node_path = NODE_PATH or resolve_executable("node")
    deno_ver = get_executable_version([deno_path, "--version"]) if deno_path else None
    node_ver = get_executable_version([node_path, "-v"]) if node_path else None

    # Test extraction
    test_url = sanitize_youtube_url(url or "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    cookie_file = create_cookie_file_from_env(YOUTUBE_COOKIES_FILE or YOUTUBE_COOKIES_B64, "quickdownload-debug-")

    extraction_start = time.time()
    extraction_result: dict[str, Any] = {
        "url": test_url,
        "success": False,
    }

    fast_opts: Any = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 5,
        "retries": 0,
        "remote_components": ["ejs:github"],
        "nocheckcertificate": True,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    js_cfg = get_js_runtimes_config()
    if js_cfg:
        fast_opts["js_runtimes"] = js_cfg
    if YOUTUBE_PROXY:
        fast_opts["proxy"] = YOUTUBE_PROXY
    if cookie_file:
        fast_opts["cookiefile"] = cookie_file

    client_probe_results = []
    success_info = None

    for candidate_tuple in YOUTUBE_CLIENT_CHAIN:
        c_name = candidate_tuple[0]
        c_args = candidate_tuple[1]
        c_use_cookies = candidate_tuple[2] if len(candidate_tuple) > 2 else True

        c_opts = dict(fast_opts)
        if not c_use_cookies:
            c_opts.pop("cookiefile", None)
        if c_args:
            c_opts["extractor_args"] = {"youtube": {"player_client": c_args}}
        if YT_PO_TOKEN:
            if "extractor_args" not in c_opts:
                c_opts["extractor_args"] = {"youtube": {}}
            c_opts["extractor_args"]["youtube"]["po_token"] = [YT_PO_TOKEN]

        t0 = time.time()
        try:
            with yt_dlp.YoutubeDL(cast(Any, c_opts)) as ydl:
                info = ydl.extract_info(test_url, download=False)
                if info and (info.get("formats") or info.get("title")):
                    duration_ms = round((time.time() - t0) * 1000, 2)
                    client_probe_results.append({
                        "client": c_name,
                        "success": True,
                        "duration_ms": duration_ms,
                        "formats_count": len(info.get("formats", [])),
                    })
                    if not success_info:
                        success_info = info
                    break
        except Exception as e:
            duration_ms = round((time.time() - t0) * 1000, 2)
            c_code, c_msg = classify_youtube_error(e)
            client_probe_results.append({
                "client": c_name,
                "success": False,
                "duration_ms": duration_ms,
                "code": c_code,
                "error": str(e)[:300],
            })

    total_duration_ms = round((time.time() - extraction_start) * 1000, 2)
    if success_info:
        extraction_result["success"] = True
        extraction_result["title"] = success_info.get("title")
        extraction_result["formats_count"] = len(success_info.get("formats", []))
        extraction_result["duration_ms"] = total_duration_ms
        extraction_result["client_probes"] = client_probe_results
    else:
        last_err = client_probe_results[-1] if client_probe_results else None
        extraction_result["success"] = False
        extraction_result["duration_ms"] = total_duration_ms
        extraction_result["last_error"] = last_err
        extraction_result["client_probes"] = client_probe_results

    if cookie_file and os.path.exists(cookie_file) and cookie_file != YOUTUBE_COOKIES_FILE:
        try:
            os.unlink(cookie_file)
        except Exception:
            pass

    return {
        "success": True,
        "diagnostics": {
            "yt_dlp_version": yt_ver,
            "ffmpeg": {
                "configured": bool(FFMPEG_PATH),
                "path": FFMPEG_PATH,
                "version": ffmpeg_ver,
            },
            "deno": {
                "configured": bool(deno_path),
                "path": deno_path,
                "version": deno_ver,
            },
            "node": {
                "configured": bool(node_path),
                "path": node_path,
                "version": node_ver,
            },
            "python": {
                "version": sys.version.split()[0],
                "executable": sys.executable,
            },
            "system": {
                "platform": platform.platform(),
                "os": os.name,
                "arch": platform.machine(),
            },
            "auth_and_network": {
                "youtube_cookies_configured": bool(YOUTUBE_COOKIES_B64 or YOUTUBE_COOKIES_FILE),
                "youtube_cookie_file_active": bool(cookie_file and os.path.isfile(cookie_file)),
                "youtube_cookie_file_size": os.path.getsize(cookie_file) if cookie_file and os.path.isfile(cookie_file) else 0,
                "youtube_proxy_configured": bool(YOUTUBE_PROXY),
                "po_token_configured": bool(YT_PO_TOKEN),
            },
        },
        "test_extraction": extraction_result,
    }


@app.get("/download-folder")
@app.get("/api/download-folder")
def download_folder():
    return {
        "success": True,
        "folder": DOWNLOAD_DIR,
        "exists": os.path.exists(DOWNLOAD_DIR),
    }


@app.get("/download-file")
@app.get("/api/download-file")
def download_file(filename: str):
    safe_name = os.path.basename(filename)
    file_path = os.path.join(DOWNLOAD_DIR, safe_name)

    # 1. Direct match if already present
    if os.path.isfile(file_path) and os.path.getsize(file_path) > 1000:
        media_type, _ = mimetypes.guess_type(file_path)
        return FileResponse(
            file_path,
            media_type=media_type or "application/octet-stream",
            filename=safe_name,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # 2. Check alias map
    if safe_name in FILE_NAME_ALIASES:
        aliased = FILE_NAME_ALIASES[safe_name]
        if os.path.isfile(aliased) and os.path.getsize(aliased) > 1000:
            media_type, _ = mimetypes.guess_type(aliased)
            return FileResponse(
                aliased,
                media_type=media_type or "application/octet-stream",
                filename=os.path.basename(aliased),
                headers={"Access-Control-Allow-Origin": "*"},
            )

    # 3. If a background download is currently underway for this file or video ID, wait for it
    event = None
    with ACTIVE_DOWNLOAD_LOCK:
        event = ACTIVE_DOWNLOAD_EVENTS.get(safe_name)
        if not event:
            for key, ev in ACTIVE_DOWNLOAD_EVENTS.items():
                if key in safe_name:
                    event = ev
                    break

    if event:
        event.wait(timeout=50)

    # 4. Check again after waiting
    if os.path.isfile(file_path) and os.path.getsize(file_path) > 1000:
        media_type, _ = mimetypes.guess_type(file_path)
        return FileResponse(
            file_path,
            media_type=media_type or "application/octet-stream",
            filename=safe_name,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # 5. Check alias map again
    if safe_name in FILE_NAME_ALIASES:
        aliased = FILE_NAME_ALIASES[safe_name]
        if os.path.isfile(aliased) and os.path.getsize(aliased) > 1000:
            media_type, _ = mimetypes.guess_type(aliased)
            return FileResponse(
                aliased,
                media_type=media_type or "application/octet-stream",
                filename=os.path.basename(aliased),
                headers={"Access-Control-Allow-Origin": "*"},
            )

    # 6. Fallback search by title / candidate in DOWNLOAD_DIR
    fallback_path = find_downloaded_file(title=safe_name) or find_downloaded_file()
    if fallback_path and os.path.isfile(fallback_path) and os.path.getsize(fallback_path) > 1000:
        media_type, _ = mimetypes.guess_type(fallback_path)
        return FileResponse(
            fallback_path,
            media_type=media_type or "application/octet-stream",
            filename=os.path.basename(fallback_path),
            headers={"Access-Control-Allow-Origin": "*"},
        )

    raise HTTPException(status_code=404, detail="File not found or has expired.")


# Unified Download Endpoint (Step 4 & 7)
@app.post("/download")
@app.post("/api/download")
def download_media(payload: DownloadRequest, request: Request):
    url = (payload.url or "").strip()
    platform = (payload.platform or "").strip()

    if not url:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Please enter a valid video link.",
        )

    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        payload.url = url

    # Auto-detect platform if not provided or set to auto
    if not platform or platform.lower() in ("auto", "all", "detect", "auto-detect", "universal"):
        if is_valid_youtube_url(url):
            platform = "YouTube"
        elif is_valid_instagram_url(url):
            platform = "Instagram"
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported platform or URL. Supported platforms: YouTube, Instagram.",
            )

    payload.platform = platform
    if platform.lower() == "youtube":
        return download_youtube(payload, request)
    elif platform.lower() == "instagram":
        return download_instagram(payload, request)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform: {platform}. Supported: YouTube, Instagram.",
        )


# YouTube Player Client Fallback Sequence
# (client_name, player_client_args, use_cookies)
# If cookies are valid, 'default' and 'web' use them for full 1080p+ stream URLs.
# If cookies expire/rotate, 'android_nocookies' and 'ios_nocookies' bypass cookie challenge.
YOUTUBE_CLIENT_CHAIN: list[tuple[str, list[str] | None, bool]] = [
    ("default", None, True),
    ("web", ["web"], True),
    ("android", ["android"], True),
    ("android_nocookies", ["android"], False),
    ("ios_nocookies", ["ios"], False),
]


def perform_youtube_download(
    youtube_url: str,
    expected_filename: str,
    video_id: str,
    quality: str = "720p",
    cookie_file: str | None = None,
    player_client: list[str] | None = None,
):
    event = None
    with ACTIVE_DOWNLOAD_LOCK:
        event = ACTIVE_DOWNLOAD_EVENTS.get(expected_filename)
        if not event:
            event = threading.Event()
            ACTIVE_DOWNLOAD_EVENTS[expected_filename] = event
            if video_id:
                ACTIVE_DOWNLOAD_EVENTS[video_id] = event

    target_path = os.path.join(DOWNLOAD_DIR, expected_filename)
    if os.path.isfile(target_path) and os.path.getsize(target_path) > 1000:
        event.set()
        return

    output_template = os.path.join(DOWNLOAD_DIR, "%(title).50s-%(id)s" + (f"-{quality}" if quality != "720p" else "") + ".%(ext)s")
    is_audio = quality.lower() in ("mp3", "audio")

    if is_audio:
        ydl_format = "bestaudio/best"
    elif quality.lower() == "1080p":
        ydl_format = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    elif quality.lower() in ("360p", "480p"):
        ydl_format = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best"
    else:
        ydl_format = "18/22/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best"

    ydl_options: Any = {
        "format": ydl_format,
        "outtmpl": output_template,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG_PATH or FFMPEG_DIR,
        "concurrent_fragment_downloads": 4,
        "buffersize": 1048576,
        "quiet": True,
        "no_warnings": True,
        "skip_download": False,
        "restrictfilenames": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "remote_components": ["ejs:github"],
        "socket_timeout": 15,
        "retries": 2,
        "fragment_retries": 2,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if player_client:
        ydl_options["extractor_args"] = {"youtube": {"player_client": player_client}}
    if YT_PO_TOKEN:
        if "extractor_args" not in ydl_options:
            ydl_options["extractor_args"] = {"youtube": {}}
        ydl_options["extractor_args"]["youtube"]["po_token"] = [YT_PO_TOKEN]

    if is_audio:
        ydl_options["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        ydl_options["merge_output_format"] = "mp4"
        ydl_options["postprocessor_args"] = {"ffmpeg": ["-c", "copy"]}

    js_cfg = get_js_runtimes_config()
    if js_cfg:
        ydl_options["js_runtimes"] = js_cfg
    if YOUTUBE_PROXY:
        ydl_options["proxy"] = YOUTUBE_PROXY
    if cookie_file:
        ydl_options["cookiefile"] = cookie_file

    try:
        downloaded_info = None
        # Try primary options first
        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_options)) as ydl:
                downloaded_info = ydl.extract_info(youtube_url, download=True)
        except Exception as primary_err:
            print("PRIMARY YOUTUBE DOWNLOAD FAILED, RETRYING WITH FALLBACK CHAIN:", repr(primary_err))
            for candidate_tuple in YOUTUBE_CLIENT_CHAIN:
                candidate_name = candidate_tuple[0]
                candidate_client = candidate_tuple[1]
                candidate_use_cookies = candidate_tuple[2] if len(candidate_tuple) > 2 else True

                if candidate_client == player_client:
                    continue
                fb_opts = dict(ydl_options)
                if not candidate_use_cookies:
                    fb_opts.pop("cookiefile", None)
                if candidate_client:
                    fb_opts["extractor_args"] = {"youtube": {"player_client": candidate_client}}
                else:
                    fb_opts.pop("extractor_args", None)
                try:
                    with yt_dlp.YoutubeDL(cast(Any, fb_opts)) as ydl:
                        downloaded_info = ydl.extract_info(youtube_url, download=True)
                    if downloaded_info:
                        print(f"FALLBACK YOUTUBE DOWNLOAD SUCCEEDED WITH '{candidate_name}'")
                        break
                except Exception as fb_err:
                    print(f"Fallback download with '{candidate_name}' failed:", repr(fb_err))

        if downloaded_info:
            title = downloaded_info.get("title") or "youtube-video"
            downloaded_file = find_downloaded_file(downloaded_info, title) or find_downloaded_file()
            if downloaded_file and os.path.isfile(downloaded_file):
                actual_name = os.path.basename(downloaded_file)
                FILE_NAME_ALIASES[expected_filename] = downloaded_file
                if video_id:
                    FILE_NAME_ALIASES[video_id] = downloaded_file
                if actual_name != expected_filename:
                    alias_path = os.path.join(DOWNLOAD_DIR, expected_filename)
                    if not os.path.exists(alias_path):
                        try:
                            if hasattr(os, "link"):
                                os.link(downloaded_file, alias_path)
                            else:
                                shutil.copyfile(downloaded_file, alias_path)
                        except Exception:
                            pass
    except Exception as err:
        print(f"Error in background download for {youtube_url}:", repr(err))
    finally:
        event.set()
        if cookie_file and os.path.exists(cookie_file) and cookie_file != YOUTUBE_COOKIES_FILE and cookie_file != LOCAL_YT_COOKIES:
            try:
                os.unlink(cookie_file)
            except Exception:
                pass


@app.post("/download-youtube")
@app.post("/api/download-youtube")
def download_youtube(payload: DownloadRequest, request: Request):
    youtube_url = sanitize_youtube_url(payload.url)
    if not is_valid_youtube_url(youtube_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube URL. Please provide a valid YouTube video link.",
        )

    cleanup_downloads()
    now = time.time()
    quality = (payload.quality or "720p").lower().strip()
    is_audio = quality in ("mp3", "audio")

    # 1. Check in-memory metadata cache for instant response (< 5ms)
    cached_info = None
    if youtube_url in METADATA_CACHE:
        cached_data, cached_at = METADATA_CACHE[youtube_url]
        if now - cached_at < CACHE_TTL_SECONDS:
            cached_info = cached_data

    cookie_file = create_cookie_file_from_env(YOUTUBE_COOKIES_FILE or YOUTUBE_COOKIES_B64, "quickdownload-youtube-")
    info = cached_info
    successful_client = None

    if not info:
        fast_opts: Any = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "socket_timeout": 5,
            "retries": 0,
            "remote_components": ["ejs:github"],
            "nocheckcertificate": True,
            "geo_bypass": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        js_cfg = get_js_runtimes_config()
        if js_cfg:
            fast_opts["js_runtimes"] = js_cfg
        if YOUTUBE_PROXY:
            fast_opts["proxy"] = YOUTUBE_PROXY
        if cookie_file:
            fast_opts["cookiefile"] = cookie_file

        last_error = None
        for candidate_tuple in YOUTUBE_CLIENT_CHAIN:
            client_name = candidate_tuple[0]
            client_args = candidate_tuple[1]
            client_use_cookies = candidate_tuple[2] if len(candidate_tuple) > 2 else True

            candidate_opts = dict(fast_opts)
            if not client_use_cookies:
                candidate_opts.pop("cookiefile", None)
            if client_args:
                candidate_opts["extractor_args"] = {"youtube": {"player_client": client_args}}
            if YT_PO_TOKEN:
                if "extractor_args" not in candidate_opts:
                    candidate_opts["extractor_args"] = {"youtube": {}}
                candidate_opts["extractor_args"]["youtube"]["po_token"] = [YT_PO_TOKEN]

            try:
                with yt_dlp.YoutubeDL(cast(Any, candidate_opts)) as ydl:
                    extracted = ydl.extract_info(youtube_url, download=False)
                    if extracted and (extracted.get("formats") or extracted.get("title")):
                        info = extracted
                        successful_client = client_args
                        print(f"[yt-dlp] Client '{client_name}' extraction SUCCEEDED for {youtube_url}")
                        break
            except Exception as client_err:
                last_error = client_err
                print(f"[yt-dlp] Client '{client_name}' extraction failed for {youtube_url}: {repr(client_err)}")
                err_str = str(client_err).lower()
                if any(x in err_str for x in ["video unavailable", "private video", "this video has been removed", "does not exist"]):
                    break
                continue

        if not info and last_error:
            cleanup_failed_artifacts()
            code, detail = classify_youtube_error(last_error)

            # Log FULL underlying error on server console (as required by Step 1)
            yt_active_version = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
            print("=" * 70)
            print(f"[yt-dlp ERROR] YouTube extraction completely failed for URL: {youtube_url}")
            print(f"[yt-dlp ERROR] Active yt-dlp version: {yt_active_version}")
            print(f"[yt-dlp ERROR] Granular error code: {code}")
            print(f"[yt-dlp ERROR] Last exception class: {type(last_error).__name__}")
            print(f"[yt-dlp ERROR] Exception detail: {str(last_error)}")
            print("[yt-dlp ERROR] Traceback:")
            print(traceback.format_exc())
            print("=" * 70)

            raise HTTPException(
                status_code=400,
                detail={
                    "error": detail,
                    "detail": detail,
                    "code": code,
                    "raw_error": str(last_error)[:200],
                },
            )

        if info:
            METADATA_CACHE[youtube_url] = (info, now)

    if not info:
        raise HTTPException(
            status_code=500,
            detail="YouTube metadata extraction returned no results.",
        )

    title = info.get("title") or "youtube-video"
    video_id = str(info.get("id") or "video")

    # Determine media badge (Shorts vs Video)
    duration = info.get("duration") or 0
    is_shorts = "/shorts/" in youtube_url or (duration <= 60 and (info.get("height") or 0) > (info.get("width") or 0))
    media_badge = "YouTube Shorts" if is_shorts else "YouTube Video"

    # Inspect formats to find available resolutions & sizes
    has_1080p = False
    size_1080 = None
    size_720 = None
    size_360 = None
    size_audio = None

    for f in info.get("formats", []):
        h = f.get("height") or 0
        sz = f.get("filesize") or f.get("filesize_approx")
        if h >= 1080:
            has_1080p = True
            if sz and (not size_1080 or sz > size_1080):
                size_1080 = sz
        elif h >= 720:
            if sz and (not size_720 or sz > size_720):
                size_720 = sz
        elif h >= 360:
            if sz and (not size_360 or sz > size_360):
                size_360 = sz
        if f.get("vcodec") == "none" and sz:
            if not size_audio or sz > size_audio:
                size_audio = sz

    qualities = []
    if has_1080p:
        qualities.append({
            "id": "1080p",
            "label": "MP4 1080p",
            "quality": "1080p",
            "ext": "mp4",
            "type": "video",
            "badge": "Full HD",
            "filesize": size_1080,
        })
    qualities.append({
        "id": "720p",
        "label": "MP4 720p",
        "quality": "720p",
        "ext": "mp4",
        "type": "video",
        "badge": "HD • Recommended",
        "filesize": size_720 or info.get("filesize") or info.get("filesize_approx"),
        "is_default": True,
    })
    qualities.append({
        "id": "360p",
        "label": "MP4 360p",
        "quality": "360p",
        "ext": "mp4",
        "type": "video",
        "badge": "Data Saver",
        "filesize": size_360,
    })
    qualities.append({
        "id": "mp3",
        "label": "MP3 Audio",
        "quality": "mp3",
        "ext": "mp3",
        "type": "audio",
        "badge": "Audio",
        "filesize": size_audio,
    })

    # Extract direct stream URLs where available
    direct_stream_urls: dict[str, str] = {}
    for f in info.get("formats", []):
        f_url = f.get("url")
        if not f_url or not f_url.startswith("http"):
            continue
        h = f.get("height") or 0
        vcodec = f.get("vcodec") or "none"
        acodec = f.get("acodec") or "none"
        if vcodec != "none" and acodec != "none":
            if h >= 1080 and "1080p" not in direct_stream_urls:
                direct_stream_urls["1080p"] = f_url
            elif h >= 720 and "720p" not in direct_stream_urls:
                direct_stream_urls["720p"] = f_url
            elif h >= 360 and "360p" not in direct_stream_urls:
                direct_stream_urls["360p"] = f_url
        elif vcodec == "none" and acodec != "none" and "mp3" not in direct_stream_urls:
            direct_stream_urls["mp3"] = f_url

    for q in qualities:
        q["direct_url"] = direct_stream_urls.get(q["id"])

    target_ext = "mp3" if is_audio else "mp4"
    output_template = os.path.join(DOWNLOAD_DIR, "%(title).50s-%(id)s" + (f"-{quality}" if quality != "720p" else "") + ".%(ext)s")
    calc_opts = {"outtmpl": output_template, "restrictfilenames": True}
    with yt_dlp.YoutubeDL(cast(Any, calc_opts)) as calc_ydl:
        prep_name = calc_ydl.prepare_filename(info)
        base, _ = os.path.splitext(prep_name)
        file_name = os.path.basename(base) + f".{target_ext}"

    # Check if this video is already downloaded and present on disk
    existing_file = find_downloaded_file(info, title)
    filesize = None
    if existing_file and os.path.isfile(existing_file) and os.path.getsize(existing_file) > 1000:
        file_name = os.path.basename(existing_file)
        filesize = os.path.getsize(existing_file)
    else:
        # Register event and kick off background download immediately
        with ACTIVE_DOWNLOAD_LOCK:
            if file_name not in ACTIVE_DOWNLOAD_EVENTS:
                ev = threading.Event()
                ACTIVE_DOWNLOAD_EVENTS[file_name] = ev
                if video_id:
                    ACTIVE_DOWNLOAD_EVENTS[video_id] = ev
                threading.Thread(
                    target=perform_youtube_download,
                    args=(youtube_url, file_name, video_id, quality, cookie_file, successful_client),
                    daemon=True,
                ).start()

    base_url = get_public_base_url(request)
    download_url = f"{base_url}/download-file?filename={quote(file_name)}"
    direct_url = direct_stream_urls.get(quality) or direct_stream_urls.get("720p")

    return {
        "success": True,
        "status": "ready",
        "message": "YouTube video is ready to download.",
        "title": title,
        "url": youtube_url,
        "platform": "YouTube",
        "media_badge": media_badge,
        "quality": quality,
        "qualities": qualities,
        "file_name": file_name,
        "download_url": download_url,
        "direct_url": direct_url,
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel"),
        "filesize": filesize or size_720 or info.get("filesize") or info.get("filesize_approx"),
    }


@app.post("/download-instagram")
@app.post("/api/download-instagram")
def download_instagram(payload: DownloadRequest, request: Request):
    instagram_url = payload.url.strip()
    if not is_valid_instagram_url(instagram_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid Instagram URL. Please provide a valid Instagram Reel, Post, or Video link.",
        )

    cleanup_downloads()
    cookie_file = create_cookie_file_from_env(INSTAGRAM_COOKIES_FILE or INSTAGRAM_COOKIES_B64, "quickdownload-instagram-")

    output_template = os.path.join(DOWNLOAD_DIR, "%(title).50s-%(id)s.%(ext)s")
    ydl_options: Any = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH or FFMPEG_DIR,
        "postprocessor_args": {"ffmpeg": ["-c", "copy"]},
        "concurrent_fragment_downloads": 4,
        "buffersize": 524288,
        "quiet": True,
        "no_warnings": True,
        "skip_download": False,
        "restrictfilenames": True,
        "socket_timeout": 12,
        "retries": 1,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    js_cfg = get_js_runtimes_config()
    if js_cfg:
        ydl_options["js_runtimes"] = js_cfg
    if cookie_file:
        ydl_options["cookiefile"] = cookie_file

    ig_proxy = normalize_proxy_url(os.getenv("INSTAGRAM_PROXY") or os.getenv("IG_PROXY") or YOUTUBE_PROXY)
    if ig_proxy:
        ydl_options["proxy"] = ig_proxy

    try:
        with yt_dlp.YoutubeDL(cast(Any, ydl_options)) as ydl:
            info = ydl.extract_info(instagram_url, download=True)

        if not info:
            raise HTTPException(
                status_code=500,
                detail="Instagram metadata extraction returned no results.",
            )

        title = info.get("title") or "instagram-video"
        downloaded_file = find_downloaded_file(info, title) or find_downloaded_file()
        file_name = os.path.basename(downloaded_file) if downloaded_file else None

        if not file_name:
            raise HTTPException(
                status_code=500,
                detail="Instagram media file was not saved successfully.",
            )

        base_url = get_public_base_url(request)
        download_url = f"{base_url}/download-file?filename={quote(file_name)}"

        filesize = os.path.getsize(downloaded_file) if downloaded_file and os.path.exists(downloaded_file) else None
        is_reel = "/reel/" in instagram_url.lower() or "/reels/" in instagram_url.lower()
        media_badge = "Instagram Reel" if is_reel else "Instagram Video"
        qualities = [
            {
                "id": "720p",
                "label": "MP4 HD",
                "quality": "720p",
                "ext": "mp4",
                "type": "video",
                "badge": "Original HD",
                "filesize": filesize,
                "is_default": True,
            },
            {
                "id": "mp3",
                "label": "MP3 Audio",
                "quality": "mp3",
                "ext": "mp3",
                "type": "audio",
                "badge": "Audio",
                "filesize": None,
            },
        ]

        return {
            "success": True,
            "status": "ready",
            "message": "Instagram video is ready to download.",
            "title": title,
            "url": instagram_url,
            "platform": "Instagram",
            "media_badge": media_badge,
            "quality": payload.quality or "720p",
            "qualities": qualities,
            "file_name": file_name,
            "download_url": download_url,
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader") or info.get("channel"),
            "filesize": filesize,
        }

    except HTTPException:
        raise
    except Exception as error:
        msg = str(error)
        print("INSTAGRAM YT-DLP ERROR:", repr(error))
        cleanup_failed_artifacts()

        if "empty media response" in msg.lower() or "logged-in" in msg.lower() or "cookies" in msg.lower() or "login required" in msg.lower():
            detail = "This Instagram content is private or requires login. Only publicly accessible Instagram Reel/Post links can be downloaded."
            code = "PRIVATE_OR_UNAVAILABLE"
        elif "rate-limit" in msg.lower() or "429" in msg.lower():
            detail = "Instagram request was rate-limited. Please wait a few minutes and try again."
            code = "RATE_LIMITED"
        elif "not found" in msg.lower() or "does not exist" in msg.lower():
            detail = "This Instagram post or reel could not be found or has been removed."
            code = "NOT_FOUND"
        else:
            detail = "Unable to process this Instagram link from the server. Please check the link and try again."
            code = "EXTRACTION_FAILED"

        raise HTTPException(status_code=400, detail={"error": detail, "detail": detail, "code": code})
    finally:
        if cookie_file and os.path.exists(cookie_file) and cookie_file != INSTAGRAM_COOKIES_FILE:
            try:
                os.unlink(cookie_file)
            except Exception:
                pass


def check_ytdlp_update():
    """Non-blocking background check for yt-dlp library updates."""
    try:
        import subprocess, sys
        print("[Startup] Checking for yt-dlp updates in background...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--upgrade", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=45,
        )
        first_line = result.stdout.strip().split("\n")[0] if result.stdout else "done"
        print(f"[Startup] yt-dlp update check: {first_line}")
    except Exception as e:
        print(f"[Startup] yt-dlp update check skipped: {repr(e)}")


@app.on_event("startup")
def on_startup():
    ver = getattr(yt_dlp, "version", None)
    v_str = getattr(ver, "__version__", "installed") if ver else "installed"
    print(f"[Startup] QuickDownload API initializing. Active yt-dlp version: {v_str}")
    t = threading.Thread(target=check_ytdlp_update, daemon=True)
    t.start()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n==============================================")
    print(f"  QuickDownload Backend running at: http://0.0.0.0:{port}")
    print(f"==============================================\n")
    uvicorn.run(app, host="0.0.0.0", port=port)