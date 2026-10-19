"""Tovar rasmlarini Telegram'dan olib beradi: /api/img?f=<file_id>. Token sahifaga chiqmaydi."""
import json
import os
import re
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
FILE_ID = re.compile(r"^[A-Za-z0-9_-]{20,200}$")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        fid = (q.get("f") or [""])[0]
        if not BOT_TOKEN or not FILE_ID.match(fid):
            self.send_response(404)
            self.end_headers()
            return
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={fid}", timeout=8) as r:
                path = json.load(r)["result"]["file_path"]
            with urllib.request.urlopen(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}", timeout=8) as r:
                body = r.read()
        except Exception:  # noqa: BLE001
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "public, max-age=31536000, s-maxage=31536000, immutable")
        self.end_headers()
        self.wfile.write(body)
