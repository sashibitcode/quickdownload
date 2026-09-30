import base64
import json
import mimetypes
import os
import shutil
import tempfile
import time
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
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173"),
    ).split(",")
    if origin.strip()
]

PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "").strip().rstrip("/")
YOUTUBE_COOKIES_B64 = os.getenv("YOUTUBE_COOKIES_B64", "").strip()
INSTAGRAM_COOKIES_B64 = os.getenv("INSTAGRAM_COOKIES_B64", "").strip()


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


YOUTUBE_PROXY = normalize_proxy_url(os.getenv("YOUTUBE_PROXY", os.getenv("HTTP_PROXY", "")))
DOWNLOAD_DIR = os.getenv(
    "DOWNLOAD_DIR",
    os.path.join(tempfile.gettempdir(), "saveall-downloads"),
)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)



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
    if DENO_PATH:
        config["deno"] = {"path": DENO_PATH}
    if NODE_PATH:
        config["node"] = {"path": NODE_PATH}
    return config if config else None

app = FastAPI(
    title="SAVEALL API",
    description="Backend API for SAVEALL multi-platform downloader",
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
    allow_origin_regex=r"https://([a-zA-Z0-9_-]+\.)?(vercel\.app|onrender\.com)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Structured Error Handlers (Step 4 & 8)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": detail,
            "detail": detail,
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


def create_cookie_file_from_env(encoded_cookies: str, prefix: str):
    """Write base64-encoded Netscape cookies to a temp file and return path."""
    if not encoded_cookies:
        return None
    try:
        decoded = base64.b64decode(encoded_cookies, validate=True)
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
    """Normalize YouTube URL and remove playlist parameters to isolate the single video."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean
    try:
        parsed = urlparse(clean)
        # If it's a standard watch URL, preserve only the 'v' parameter
        if "youtube.com" in (parsed.netloc or "").lower() and parsed.path == "/watch":
            from urllib.parse import parse_qs, urlencode
            qs = parse_qs(parsed.query)
            if "v" in qs and qs["v"]:
                clean_query = urlencode({"v": qs["v"][0]})
                return f"{parsed.scheme}://{parsed.netloc}/watch?{clean_query}"
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


# Root and Health check endpoints (available at / and /api)
@app.get("/")
@app.get("/api")
def home():
    return {
        "success": True,
        "message": "SAVEALL API is running!",
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

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found or has expired.")

    media_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(
        file_path,
        media_type=media_type or "application/octet-stream",
        filename=safe_name,
        headers={
            "Access-Control-Allow-Origin": "*",
        },
    )


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
    cookie_file = create_cookie_file_from_env(YOUTUBE_COOKIES_B64, "saveall-youtube-")

    output_template = os.path.join(DOWNLOAD_DIR, "%(title).50s-%(id)s.%(ext)s")
    # Tier 1 format priority: Progressive 18/22 first for 1s single-stream download, then 720p multiplex
    ydl_options: Any = {
        "format": "18/22/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH or FFMPEG_DIR,
        "concurrent_fragment_downloads": 6,
        "buffersize": 1048576,
        "quiet": True,
        "no_warnings": True,
        "skip_download": False,
        "restrictfilenames": True,
        "nocheckcertificate": True,
        "remote_components": ["ejs:github"],
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
    }

    # When NO proxy is present (direct cloud datacenter connection),
    # use mobile clients to avoid datacenter bot protection
    if not YOUTUBE_PROXY:
        ydl_options["extractor_args"] = {
            "youtube": {
                "player_client": ["android", "ios", "mweb"]
            }
        }

    js_cfg = get_js_runtimes_config()
    if js_cfg:
        ydl_options["js_runtimes"] = js_cfg
    if YOUTUBE_PROXY:
        ydl_options["proxy"] = YOUTUBE_PROXY
    if cookie_file:
        ydl_options["cookiefile"] = cookie_file

    info = None
    try:
        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_options)) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
        except Exception as primary_err:
            err_str = str(primary_err).lower()
            print("YOUTUBE PRIMARY DOWNLOAD ATTEMPT ERROR:", repr(primary_err))

            # Prepare direct fallback options WITHOUT proxy
            direct_fallback_opts = dict(ydl_options)
            direct_fallback_opts.pop("proxy", None)
            direct_fallback_opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android", "ios", "mweb"]
                }
            }

            last_err = primary_err
            # Failover 1: Direct datacenter connection with Android/iOS client
            try:
                print("YOUTUBE RETRYING FAILOVER 1 (Direct connection / Mobile client)...")
                with yt_dlp.YoutubeDL(cast(Any, direct_fallback_opts)) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
            except Exception as f1_err:
                print("YOUTUBE FAILOVER 1 ERROR:", repr(f1_err))
                last_err = f1_err

                # Failover 2: Flexible transcode muxing with broader format selector
                try:
                    print("YOUTUBE RETRYING FAILOVER 2 (Flexible format & muxing)...")
                    f2_opts = dict(direct_fallback_opts)
                    f2_opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best"
                    f2_opts["extractor_args"] = {
                        "youtube": {
                            "player_client": ["ios", "android"]
                        }
                    }
                    with yt_dlp.YoutubeDL(cast(Any, f2_opts)) as ydl:
                        info = ydl.extract_info(youtube_url, download=True)
                except Exception as f2_err:
                    print("YOUTUBE FAILOVER 2 ERROR:", repr(f2_err))
                    last_err = f2_err

                    # Failover 3: Mobile Web fallback
                    try:
                        print("YOUTUBE RETRYING FAILOVER 3 (Mobile Web fallback)...")
                        f3_opts = dict(direct_fallback_opts)
                        f3_opts["extractor_args"] = {
                            "youtube": {
                                "player_client": ["mweb", "android"]
                            }
                        }
                        f3_opts["format"] = "bestvideo+bestaudio/best"
                        with yt_dlp.YoutubeDL(cast(Any, f3_opts)) as ydl:
                            info = ydl.extract_info(youtube_url, download=True)
                    except Exception as f3_err:
                        print("YOUTUBE FAILOVER 3 ERROR:", repr(f3_err))
                        last_err = f3_err

                        # Failover 4: Universal fallback without extractor args
                        try:
                            print("YOUTUBE RETRYING FAILOVER 4 (Universal fallback)...")
                            f4_opts = dict(direct_fallback_opts)
                            f4_opts.pop("extractor_args", None)
                            f4_opts["format"] = "best"
                            with yt_dlp.YoutubeDL(cast(Any, f4_opts)) as ydl:
                                info = ydl.extract_info(youtube_url, download=True)
                        except Exception as f4_err:
                            print("YOUTUBE FAILOVER 4 ERROR:", repr(f4_err))
                            raise last_err

        if not info:
            raise HTTPException(
                status_code=500,
                detail="YouTube metadata extraction returned no results.",
            )

        title = info.get("title") or "youtube-video"
        downloaded_file = find_downloaded_file(info, title) or find_downloaded_file()
        file_name = os.path.basename(downloaded_file) if downloaded_file else None

        if not file_name:
            raise HTTPException(
                status_code=500,
                detail="YouTube media file was not saved successfully.",
            )

        filesize = os.path.getsize(downloaded_file) if downloaded_file and os.path.exists(downloaded_file) else None
        base_url = get_public_base_url(request)
        download_url = f"{base_url}/download-file?filename={quote(file_name)}"

        return {
            "success": True,
            "status": "ready",
            "message": "YouTube video is ready to download.",
            "title": title,
            "url": youtube_url,
            "platform": "YouTube",
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
        print("YOUTUBE YT-DLP ERROR:", repr(error))
        cleanup_failed_artifacts()

        if "private" in msg.lower() or "unavailable" in msg.lower() or "removed" in msg.lower() or "not exist" in msg.lower():
            detail = "This YouTube video is private, restricted, or unavailable."
        elif "members only" in msg.lower() or "premium" in msg.lower() or "purchase" in msg.lower():
            detail = "This YouTube video requires membership or purchase and cannot be downloaded."
        elif "tunnel" in msg.lower() or "407" in msg.lower() or "402" in msg.lower():
            detail = "The proxy server connection failed or credentials expired. Please check your proxy settings in Render."
        elif "sign in" in msg.lower() or "bot" in msg.lower() or "429" in msg.lower() or "confirm you're not a bot" in msg.lower() or "cookies" in msg.lower():
            detail = "YouTube blocked cloud datacenter access (bot protection). Please run the local backend server (start-dev.bat) for instant downloads, or configure YOUTUBE_COOKIES_B64 in Render."
        else:
            first_line = msg.split("\n")[0].strip()
            detail = f"Unable to process this YouTube link from the server. ({first_line[:120]})"

        raise HTTPException(status_code=400, detail=detail)
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try:
                os.unlink(cookie_file)
            except Exception:
                pass


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
    cookie_file = create_cookie_file_from_env(INSTAGRAM_COOKIES_B64, "saveall-instagram-")

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
        return {
            "success": True,
            "status": "ready",
            "message": "Instagram video is ready to download.",
            "title": title,
            "url": instagram_url,
            "platform": "Instagram",
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
        elif "rate-limit" in msg.lower() or "429" in msg.lower():
            detail = "Instagram request was rate-limited. Please wait a few minutes and try again."
        elif "not found" in msg.lower() or "does not exist" in msg.lower():
            detail = "This Instagram post or reel could not be found or has been removed."
        else:
            detail = "Unable to process this Instagram link from the server. Please check the link and try again."

        raise HTTPException(status_code=400, detail=detail)
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try:
                os.unlink(cookie_file)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n==============================================")
    print(f"  SAVEALL Backend running at: http://127.0.0.1:{port}")
    print(f"==============================================\n")
    uvicorn.run(app, host="127.0.0.1", port=port)