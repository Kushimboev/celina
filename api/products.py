"""
Celina Store — bot orqali qo'shilgan tovarlar (Upstash Redis "prod" xeshi) va yashirilgan
eski tovarlar ro'yxati. Mini App products.json bilan birga shu yerni ham o'qiydi.
Manba havolalari ("src") bu yerda qaytarilmaydi — ular faqat admin uchun.
"""
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler

KV_URL = (os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL") or "").rstrip("/")
KV_TOKEN = (os.environ.get("KV_REST_API_READ_ONLY_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
            or os.environ.get("UPSTASH_REDIS_REST_TOKEN") or "")
PUBLIC_KEYS = ("id", "cat", "name", "price", "img", "sizes", "colors", "ask", "d", "t", "new", "fabric", "stock")


def load():
    if not KV_URL or not KV_TOKEN:
        return {"items": [], "hidden": [], "db": False}
    req = urllib.request.Request(KV_URL + "/pipeline", data=json.dumps([["HGETALL", "prod"], ["SMEMBERS", "hidden"]]).encode(),
                                 headers={"Authorization": "Bearer " + KV_TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=6) as r:
        prod, hidden = [x.get("result") or [] for x in json.load(r)]
    items = []
    for i in range(1, len(prod), 2):
        try:
            p = json.loads(prod[i])
            items.append({k: p[k] for k in PUBLIC_KEYS if k in p})
        except ValueError:
            continue
    items.sort(key=lambda p: p.get("t", 0), reverse=True)
    return {"items": items, "hidden": hidden, "db": True}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body, code, cache = json.dumps(load(), ensure_ascii=False).encode(), 200, "public, s-maxage=15, stale-while-revalidate=60"
        except Exception as e:  # noqa: BLE001
            print("products xato:", repr(e))
            body, code, cache = b'{"items":[],"hidden":[],"error":true}', 200, "no-store"
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)
