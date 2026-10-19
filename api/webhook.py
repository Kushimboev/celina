"""
Celina Store — Telegram bot, Vercel serverless (webhook) versiyasi.

Faqat standart kutubxona. Sozlama: Vercel'da BOT_TOKEN muhit o'zgaruvchisi.
Buyurtma raqami = admin kartochkasining message_id. Holat kartochkaning o'zida saqlanadi
(tashqi baza kerak emas): tugma callback_data = "s:<status>:<mijoz_id>:<oldindan_to'lov>".
"""
import hashlib
import html
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://celina-red.vercel.app/")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "500336914"))
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "500336914").split(",") if x.strip()}
STORE_NAME = os.environ.get("STORE_NAME", "Celina Store")
PAYMENT_TEXT = os.environ.get(
    "PAYMENT_TEXT",
    "To'lov uchun Click/Payme raqamini admin yuboradi.\nTo'lovdan keyin chek skrinshotini shu yerga tashlang.",
).replace("\\n", "\n")

STATUSES = {
    "new": ("🆕", "Yangi"),
    "confirmed": ("🕓", "Tasdiqlandi, to'lov kutilmoqda"),
    "paid": ("💳", "Oldindan to'lov qabul qilindi"),
    "ordered": ("🇨🇳", "Xitoyga buyurtma berildi"),
    "arrived": ("📦", "Toshkentga keldi"),
    "delivered": ("✅", "Yetkazildi"),
    "cancelled": ("✖️", "Bekor qilindi"),
}
FLOW = ["confirmed", "paid", "ordered", "arrived", "delivered", "cancelled"]
CUSTOMER_TEXT = {
    "confirmed": "Buyurtmangiz #{n} tasdiqlandi. Oldindan to'lov: {pre}.\n\n{pay}",
    "paid": "#{n}: to'lovingiz qabul qilindi. Tovarni Xitoydan buyurtma qilyapmiz.",
    "ordered": "#{n}: tovar Xitoyda buyurtma qilindi. Yetib kelishi taxminan 10–14 kun.",
    "arrived": "#{n}: tovaringiz Toshkentga keldi. Tez orada yetkazamiz.",
    "delivered": "#{n}: buyurtma yetkazildi. Xaridingiz uchun rahmat! Fikringizni yozib qoldirsangiz xursand bo'lamiz.",
    "cancelled": "#{n}: buyurtma bekor qilindi. Savollar bo'lsa, shu yerga yozing.",
}


def secret() -> str:
    return hashlib.sha256(("celina:" + BOT_TOKEN).encode()).hexdigest()[:48]


def api(method: str, **params):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=json.dumps(params).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def money(n) -> str:
    return f"{int(n):,}".replace(",", " ") + " so'm"


def is_admin(uid) -> bool:
    return uid in ADMIN_IDS


def main_keyboard(uid):
    rows = [[{"text": "🛍 Katalogni ochish", "web_app": {"url": WEBAPP_URL}}]]
    if is_admin(uid):
        rows.append([{"text": "🧮 Narx kalkulyatori", "web_app": {"url": WEBAPP_URL.split("#")[0] + "#admin"}}])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def status_kb(current: str, uid: int, pre: int):
    rows, row = [], []
    for st in FLOW:
        emoji, label = STATUSES[st]
        mark = "• " if st == current else ""
        row.append({"text": f"{mark}{emoji} {label.split(',')[0]}", "callback_data": f"s:{st}:{uid}:{pre}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}


def parse_order(raw: str) -> dict:
    data = json.loads(raw)
    if data.get("v") != 1:
        raise ValueError("versiya")
    items = data["i"]
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        raise ValueError("tovarlar soni")
    clean = []
    for it in items:
        q, p = int(it["q"]), int(it["p"])
        if not (1 <= q <= 20 and 0 < p < 50_000_000):
            raise ValueError("miqdor yoki narx")
        clean.append({"id": str(it["id"])[:16], "n": str(it["n"])[:60], "s": str(it.get("s", ""))[:20],
                      "c": str(it.get("c", ""))[:30], "q": q, "p": p})
    cu = data["cu"]
    sub = sum(x["q"] * x["p"] for x in clean)
    delivery = max(0, min(int(data.get("del", 0)), 200_000))
    total = sub + delivery
    return {"items": clean, "name": str(cu["n"])[:60], "phone": str(cu["ph"])[:20], "region": str(cu["r"])[:40],
            "address": str(cu["a"])[:200], "pay": str(cu.get("pay", ""))[:20], "note": str(cu.get("note", ""))[:200],
            "sub": sub, "del": delivery, "tot": total, "pre": round(total * 0.5 / 1000) * 1000}


def items_lines(items) -> str:
    out = []
    for k, it in enumerate(items, 1):
        opts = ", ".join(x for x in (it.get("s"), it.get("c")) if x)
        out.append(f"{k}. {it['n']} [{it['id']}]" + (f" — {opts}" if opts else "")
                   + f"\n    {it['q']} × {money(it['p'])} = {money(it['q'] * it['p'])}")
    return "\n".join(out)


def card_text(n, status, o, user) -> str:
    emoji, label = STATUSES[status]
    who = f"@{user.get('username')}" if user.get("username") else f"id {user.get('id')}"
    return (f"Buyurtma #{n} · {emoji} {label}\n\n{items_lines(o['items'])}\n\n"
            f"Tovarlar: {money(o['sub'])}\nYetkazish: {money(o['del'])}\nJami: {money(o['tot'])}\n"
            f"Oldindan (50%): {money(o['pre'])}\n\n"
            f"👤 {o['name']} · {who}\n📞 {o['phone']}\n📍 {o['region']}, {o['address']}\n💳 {o['pay']}"
            + (f"\n📝 {o['note']}" if o["note"] else ""))


def on_message(m):
    chat_id = m["chat"]["id"]
    user = m.get("from", {})
    uid = user.get("id")
    if "web_app_data" in m:
        try:
            o = parse_order(m["web_app_data"]["data"])
        except Exception:  # noqa: BLE001
            api("sendMessage", chat_id=chat_id, text="Buyurtmani o'qib bo'lmadi. Katalogni qayta ochib, yana urinib ko'ring.")
            return
        sent = api("sendMessage", chat_id=ADMIN_CHAT_ID, text=card_text("…", "new", o, user))
        n = sent.get("result", {}).get("message_id", "?")
        if sent.get("ok"):
            api("editMessageText", chat_id=ADMIN_CHAT_ID, message_id=n, text=card_text(n, "new", o, user),
                reply_markup=status_kb("new", uid, o["pre"]))
        api("sendMessage", chat_id=chat_id, parse_mode="HTML", reply_markup=main_keyboard(uid),
            text=(f"✅ Buyurtma <b>#{n}</b> qabul qilindi!\n\n{html.escape(items_lines(o['items']))}\n\n"
                  f"Jami: <b>{money(o['tot'])}</b>\nOldindan to'lov (50%): <b>{money(o['pre'])}</b>\n\n"
                  "Admin tez orada buyurtmani tasdiqlab, to'lov ma'lumotini yuboradi."))
        return
    text = (m.get("text") or "").strip()
    if text.startswith("/start"):
        api("sendMessage", chat_id=chat_id, parse_mode="HTML", reply_markup=main_keyboard(uid),
            text=(f"Assalomu alaykum! <b>{STORE_NAME}</b> ga xush kelibsiz.\n\n"
                  "Pastdagi <b>🛍 Katalogni ochish</b> tugmasini bosing: tovarni tanlang, razmerni belgilang va "
                  "buyurtma bering. Buyurtma raqami shu yerga keladi."))
    elif text.startswith("/id"):
        api("sendMessage", chat_id=chat_id, text=f"Sizning ID: {uid}\nShu chat ID: {chat_id}")


def on_callback(c):
    uid = c["from"]["id"]
    if not is_admin(uid):
        api("answerCallbackQuery", callback_query_id=c["id"], text="Faqat admin uchun", show_alert=True)
        return
    try:
        _, st, cust, pre = c["data"].split(":")
        cust, pre = int(cust), int(pre)
    except ValueError:
        api("answerCallbackQuery", callback_query_id=c["id"])
        return
    msg = c.get("message") or {}
    n = msg.get("message_id")
    lines = (msg.get("text") or "").split("\n")
    if st not in STATUSES or not lines:
        api("answerCallbackQuery", callback_query_id=c["id"])
        return
    emoji, label = STATUSES[st]
    new_first = f"Buyurtma #{n} · {emoji} {label}"
    if lines[0] == new_first:
        api("answerCallbackQuery", callback_query_id=c["id"], text="Status allaqachon shu")
        return
    lines[0] = new_first
    api("editMessageText", chat_id=msg["chat"]["id"], message_id=n, text="\n".join(lines),
        reply_markup=status_kb(st, cust, pre))
    r = api("sendMessage", chat_id=cust, text=CUSTOMER_TEXT[st].format(n=n, pre=money(pre), pay=PAYMENT_TEXT))
    if r.get("ok"):
        api("answerCallbackQuery", callback_query_id=c["id"], text=f"{label} ✓")
    else:
        api("answerCallbackQuery", callback_query_id=c["id"], text="Status saqlandi, mijozga xabar yetmadi", show_alert=True)


class handler(BaseHTTPRequestHandler):
    def _reply(self, code=200, body=b"ok"):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._reply(200, b"Celina bot ishlayapti" if BOT_TOKEN else b"BOT_TOKEN sozlanmagan")

    def do_POST(self):
        if not BOT_TOKEN or self.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret():
            self._reply(403, b"forbidden")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            upd = json.loads(self.rfile.read(length) or b"{}")
            if "message" in upd:
                on_message(upd["message"])
            elif "callback_query" in upd:
                on_callback(upd["callback_query"])
        except Exception as e:  # noqa: BLE001 — Telegram qayta yubormasligi uchun 200 qaytaramiz
            print("xato:", repr(e))
        self._reply()
