import sys
import os
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import json

backend_dir = os.path.join(os.getcwd(), "backend")
sys.path.insert(0, backend_dir)

from main import app, DOWNLOAD_DIR, cleanup_failed_artifacts, cleanup_downloads

print("=" * 60)
print("RUNNING QUICKDOWNLOAD LOCAL TEST SUITE")
print("=" * 60)

# Start uvicorn background process on port 8009
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8009"],
    cwd=backend_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

time.sleep(2)

base_url = "http://127.0.0.1:8009"

try:
    # 1. Health check
    print("\n--- Test 1: Health Endpoint ---")
    req = urllib.request.Request(f"{base_url}/health")
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode())
        print("Health status code:", resp.status)
        print("Health response:", body)
        assert resp.status == 200
        assert body.get("success") is True

    # 2. CORS Preflight Check from Vercel domain
    print("\n--- Test 2: CORS Preflight from Vercel ---")
    req = urllib.request.Request(
        f"{base_url}/download",
        headers={
            "Origin": "https://quick-d.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
        method="OPTIONS",
    )
    with urllib.request.urlopen(req) as resp:
        print("OPTIONS status code:", resp.status)
        cors_header = resp.headers.get("access-control-allow-origin")
        print("CORS Allow-Origin:", cors_header)
        assert resp.status == 200
        assert cors_header == "https://quick-d.vercel.app"

    # 3. Invalid URL
    print("\n--- Test 3: Invalid URL ---")
    req = urllib.request.Request(
        f"{base_url}/download",
        data=json.dumps({"url": "https://invalid-site-domain.com/video"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        print("ERROR: Expected 400 error")
    except urllib.error.HTTPError as err:
        body = json.loads(err.read().decode())
        print("Invalid URL HTTP code:", err.code)
        print("Invalid URL response JSON:", body)
        assert err.code == 400
        assert body.get("success") is False
        assert "Unsupported" in body.get("detail", "")

    # 4. Non-existent / Unavailable YouTube URL
    print("\n--- Test 4: Restricted / Unavailable YouTube URL ---")
    req = urllib.request.Request(
        f"{base_url}/download",
        data=json.dumps({"url": "https://www.youtube.com/watch?v=00000000000"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        raise AssertionError("Expected 400 error for unavailable video")
    except urllib.error.HTTPError as err:
        body = json.loads(err.read().decode())
        print("Restricted URL HTTP code:", err.code)
        print("Restricted URL response JSON:", body)
        assert err.code == 400
        assert body.get("success") is False
        detail = body.get("detail", "")
        print("Verified user-friendly message:", detail)
        assert "Configure YOUTUBE_COOKIES_B64" not in detail
        assert "restricted datacenter" not in detail
        assert "private, restricted, or unavailable" in detail

    # 5. Valid Supported YouTube URL
    print("\n--- Test 5: Valid YouTube URL ---")
    req = urllib.request.Request(
        f"{base_url}/download",
        data=json.dumps({"url": "https://www.youtube.com/watch?v=aqz-KE-bpKQ"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode())
        print("Valid YouTube download response status:", resp.status)
        print("Title:", body.get("title"))
        print("File name:", body.get("file_name"))
        print("Download URL:", body.get("download_url"))
        assert resp.status == 200
        assert body.get("success") is True
        file_name = body.get("file_name")

    # 6. File Download Endpoint
    print("\n--- Test 6: File Download Endpoint ---")
    file_req = urllib.request.Request(f"{base_url}/download-file?filename={urllib.parse.quote(file_name)}")
    with urllib.request.urlopen(file_req) as file_resp:
        content_type = file_resp.headers.get("content-type")
        content_length = file_resp.headers.get("content-length")
        print("File response status:", file_resp.status)
        print("Content-Type:", content_type)
        print("Content-Length (bytes):", content_length)
        assert file_resp.status == 200
        assert int(content_length) > 1000

    # 7. Check Download Directory & Cleanup
    print("\n--- Test 7: Download Directory & Temp Artifact Cleanup ---")
    cleanup_failed_artifacts()
    remaining_files = os.listdir(DOWNLOAD_DIR)
    part_files = [f for f in remaining_files if f.endswith((".part", ".ytdl", ".temp"))]
    print("Files in download dir:", len(remaining_files))
    print("Temporary/part files present:", part_files)
    assert len(part_files) == 0, f"Found leftover part files: {part_files}"

    # 8. Render Production Backend Connectivity Check
    print("\n--- Test 8: Live Render Backend Health Check ---")
    try:
        render_req = urllib.request.Request(
            "https://quickdownload-api.onrender.com/health",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(render_req, timeout=15) as r_resp:
            r_body = json.loads(r_resp.read().decode())
            print("Render production /health status:", r_resp.status)
    except Exception as r_err:
        print("Render production health check note (may be sleeping/waking):", r_err)

    # 9. Debug Endpoint Check (/debug/yt)
    print("\n--- Test 9: YouTube Debug Diagnostics Endpoint ---")
    debug_req = urllib.request.Request(f"{base_url}/debug/yt")
    with urllib.request.urlopen(debug_req, timeout=25) as d_resp:
        d_body = json.loads(d_resp.read().decode())
        print("Debug endpoint status:", d_resp.status)
        print("Debug yt-dlp version:", d_body.get("diagnostics", {}).get("yt_dlp_version"))
        print("Debug node:", d_body.get("diagnostics", {}).get("node"))
        print("Debug extraction success:", d_body.get("test_extraction", {}).get("success"))
        assert d_resp.status == 200
        assert d_body.get("success") is True
        assert "diagnostics" in d_body

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

finally:
    server.terminate()
    server.wait()
