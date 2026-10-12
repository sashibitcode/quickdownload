import urllib.request
import json

KEY = "0d22ea672b1248a38a7c295792d4f826"
HOST = "quick-d.vercel.app"
URL_LIST = [
    "https://quick-d.vercel.app/",
    "https://quick-d.vercel.app/llms.txt",
    "https://quick-d.vercel.app/llms-full.txt",
    "https://quick-d.vercel.app/sitemap.xml"
]

payload = {
    "host": HOST,
    "key": KEY,
    "keyLocation": f"https://{HOST}/{KEY}.txt",
    "urlList": URL_LIST
}

req = urllib.request.Request(
    "https://api.indexnow.org/indexnow",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"}
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"IndexNow submitted successfully! HTTP Status: {resp.status}")
except Exception as e:
    print(f"IndexNow submission notice: {e}")
