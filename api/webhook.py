"""
Celina Store — Telegram bot, Vercel serverless (webhook) versiyasi.

Faqat standart kutubxona. Sozlama: Vercel'da BOT_TOKEN muhit o'zgaruvchisi.
Buyurtma raqami = admin kartochkasining message_id. Holat kartochkaning o'zida saqlanadi:
tugma callback_data = "s:<status>:<mijoz_id>:<oldindan_to'lov>".

Admin botga PDD/Taobao/1688 havolasi + rasmlar + "¥45" yuborsa, qoralama tuziladi va
"✅ Katalogga" bosilganda tovar Upstash Redis'ga yoziladi (Mini App /api/products orqali o'qiydi).
Redis kalitlari: d:<uid> (qoralama), d:<uid>:img (rasmlar), prod (tovarlar), src (manba havolalari,
faqat admin uchun), hidden (yashirilgan eski tovarlar), cfg (kurslar).
"""
import hashlib
import html
import json
import math
import os
import random
import re
import time
import urllib.parse
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

KV_URL = (os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL") or "").rstrip("/")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN") or ""

# Narx formulasi — index.html dagi CONFIG bilan bir xil. Kurslarni /kurs bilan o'zgartirish mumkin.
RATES = {"usd": 11963, "cny": 1803}
CARGO_USD_PER_KG, AGENT_FEE, PACKING, BUFFER = 5.5, 0.08, 2000, 0.07
CATS = {  # id: (nomi, ustama koeffitsienti, standart og'irlik g, qisqa nom)
    "kiyim": ("Kiyim", 2.5, 450, "Kiyim"),
    "pijama": ("Pijama va ichki kiyim", 2.5, 420, "Pijama"),
    "oyoq": ("Oyoq kiyim", 2.3, 600, "Oyoq"),
    "sumka": ("Sumka va hamyon", 2.3, 550, "Sumka"),
    "bolalar": ("Bolalar", 2.5, 300, "Bolalar"),
    "aksessuar": ("Aksessuar", 3.0, 150, "Aksess."),
    "kosmetika": ("Kosmetika", 2.5, 200, "Kosmet."),
    "uy": ("Uy-ro'zg'or", 2.5, 400, "Uy"),
}
SIZED_CATS = {"kiyim", "pijama", "oyoq", "bolalar"}
CAT_WORDS = [  # tartib muhim: "ichki kiyim" -> pijama, "kiyim" dan oldin
    ("pijama", "pijama pizhama пижам ichki ichkiyim trusik trusi lifchik byustgalter xalat халат бель"),
    ("bolalar", "bolalar bola детск ребен kids"),
    ("oyoq", "krossovka krasovka кроссов tufli туфл oyoq shippak tapochka тапоч botinka ботин etik сапог sandal сандал обув"),
    ("sumka", "sumka сумк hamyon кошел ryukzak рюкзак"),
    ("kosmetika", "kosmetika косметик krem крем pomada помад atir parfyum духи"),
    ("aksessuar", "aksessuar аксессуар soat часы uzuk кольц sirg серьг zirak kamar ремен sharf шарф ro'mol kepka ko'zoynak очки"),
    ("uy", "oshxona кухн idish посуд sochiq полотен choyshab постел"),
    ("kiyim", "kiyim одежд ko'ylak koylak plat платье futbolka футболк shim брюк jinsi джинс yubka юбк kurtka куртк palto пальто kofta кофт svitr свитер"),
]
SIZE_ORDER = ["XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]


class KVError(Exception):
    pass


def kv(*cmds):
    """Upstash REST pipeline. kv(["GET","a"], ["SET","b","1"]) -> [natija, natija]."""
    if not KV_URL or not KV_TOKEN:
        raise KVError("Baza ulanmagan (KV_REST_API_URL yo'q)")
    body = json.dumps([[str(a) for a in c] for c in cmds]).encode()
    req = urllib.request.Request(KV_URL + "/pipeline", data=body,
                                 headers={"Authorization": "Bearer " + KV_TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=6) as r:
        out = json.load(r)
    for x in out:
        if isinstance(x, dict) and x.get("error"):
            raise KVError(x["error"])
    return [x.get("result") if isinstance(x, dict) else x for x in out]


def pairs(flat):
    flat = flat or []
    return {flat[i]: flat[i + 1] for i in range(0, len(flat) - 1, 2)}


def rates():
    try:
        cfg = pairs(kv(["HGETALL", "cfg"])[0])
        return {"usd": float(cfg.get("usd") or RATES["usd"]), "cny": float(cfg.get("cny") or RATES["cny"])}
    except Exception:  # noqa: BLE001
        return dict(RATES)


def round_psy(x):
    r = math.ceil(x / 10000) * 10000 - 1000
    if r < x:
        r += 10000
    return int(r)


def calc(cny, grams, mult, rt):
    goods = cny * rt["cny"]
    cargo = grams / 1000 * CARGO_USD_PER_KG * rt["usd"]
    base = goods + cargo + goods * AGENT_FEE + PACKING
    landed = base * (1 + BUFFER)
    return {"landed": int(landed), "sale": round_psy(landed * mult)}


def expand_sizes(raw):
    out = []
    for tok in re.split(r"[,\s/;]+", raw.upper().replace("–", "-").replace("XXL", "2XL").replace("XXXL", "3XL")):
        if not tok:
            continue
        m = re.fullmatch(r"(\d{2,3})-(\d{2,3})", tok)
        if m:
            a, b = int(m[1]), int(m[2])
            if a >= 80 and a % 5 == 0 and b % 5 == 0 and 0 < b - a <= 80:  # bolalar: 90-130
                out += [str(x) for x in range(a, b + 1, 10 if (b - a) % 10 == 0 else 5)]
                continue
            if 0 < b - a <= 15:  # oyoq: 36-41
                out += [str(x) for x in range(a, b + 1)]
                continue
        m = re.fullmatch(r"([0-9]?X*[SML]|[2-5]XL)-([0-9]?X*[SML]|[2-5]XL)", tok)
        if m and m[1] in SIZE_ORDER and m[2] in SIZE_ORDER and SIZE_ORDER.index(m[1]) < SIZE_ORDER.index(m[2]):
            out += SIZE_ORDER[SIZE_ORDER.index(m[1]):SIZE_ORDER.index(m[2]) + 1]
            continue
        out.append(tok[:8])
    seen = []
    for s in out:
        if s not in seen:
            seen.append(s)
    return seen[:15]


def detect_cat(text):
    low = " " + text.lower().replace("’", "'").replace("‘", "'") + " "
    for cat, words in CAT_WORDS:
        for w in words.split():
            if re.search(r"(?<![a-zа-яё'])" + re.escape(w), low):
                return cat
    return None


def parse_caption(text):
    """Admin matnidan: havola, ¥ narx, og'irlik, razmer, tayyor narx, kategoriya, nom."""
    d, t = {}, " " + (text or "") + " "
    m = re.search(r"https?://\S+", t)
    if m:
        d["url"] = m[0].rstrip(").,;】")[:500]
        t = t.replace(m[0], " ")
    m = re.search(r"(?:^|\s)(?:=|sotuv\s*:?\s*|narx\s*:?\s*)(\d[\d  ]{3,}\d)(?:\s*so'?m)?", t, re.I)
    if m:
        d["price"] = int(re.sub(r"\D", "", m[1]))
        t = t.replace(m[0], " ")
    m = (re.search(r"[¥￥]\s*(\d+(?:[.,]\d+)?)", t)
         or re.search(r"(\d+(?:[.,]\d+)?)\s*(?:¥|￥|元|yuan|yuan|cny|rmb|юан\w*)", t, re.I))
    if m:
        d["cny"] = float(m[1].replace(",", "."))
        t = t.replace(m[0], " ")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kg|кг)\b", t, re.I)
    if m:
        d["kg"] = float(m[1].replace(",", "."))
        t = t.replace(m[0], " ")
    else:
        m = re.search(r"(\d{2,4})\s*(?:g|gr|г|гр)\b", t, re.I)
        if m:
            d["kg"] = int(m[1]) / 1000
            t = t.replace(m[0], " ")
    m = re.search(r"(?<![A-Za-zА-Яа-яЁё'])(?:razmer|размер|r|р)\s*[:：=]\s*([A-Za-z0-9 ,/;\-–]+)", t, re.I)
    if m:
        d["sizes"] = expand_sizes(m[1])
        t = t.replace(m[0], " ")
    cat = detect_cat(t)
    if cat:
        d["cat"] = cat
    # nom: xitoycha matn, belgilar va heshteglarsiz qolgan qism
    t = re.sub(r"[　-〿㐀-鿿＀-￯【】「」]+", " ", t)
    t = re.sub(r"#\w+|[|*_~`<>]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–,.:;")
    if len(t) >= 3:
        d["name"] = (t[0].upper() + t[1:])[:60]
    return d


def goods_id(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url or "").query)
    for k in ("goods_id", "id", "offerId", "itemId"):
        if q.get(k):
            return q[k][0]
    m = re.search(r"/offer/(\d+)", url or "")
    return m[1] if m else ""


def draft_load(uid):
    h, imgs = kv(["HGETALL", f"d:{uid}"], ["LRANGE", f"d:{uid}:img", 0, 11])
    d = pairs(h)
    for k in ("cny", "kg"):
        if d.get(k):
            d[k] = float(d[k])
    if d.get("price"):
        d["price"] = int(d["price"])
    d["sizes"] = json.loads(d["sizes"]) if d.get("sizes") else []
    d["img"] = imgs or []
    return d


def draft_save(uid, fields):
    flat = []
    for k, v in fields.items():
        flat += [k, json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v]
    if flat:
        kv(["HSET", f"d:{uid}", *flat], ["EXPIRE", f"d:{uid}", 172800])


def draft_price(d, rt=None):
    cat = CATS.get(d.get("cat") or "kiyim", CATS["kiyim"])
    grams = (d.get("kg") or 0) * 1000 or cat[2]
    if d.get("cny"):
        c = calc(d["cny"], grams, cat[1], rt or rates())
    else:
        c = {"landed": 0, "sale": 0}
    sale = d.get("price") or c["sale"]
    return {"sale": sale, "landed": c["landed"], "grams": grams, "auto_kg": not d.get("kg")}


def draft_text(d):
    cat_id = d.get("cat") or "kiyim"
    p = draft_price(d)
    lines = ["🆕 Yangi tovar — qoralama", ""]
    lines.append(f"Nomi: {d.get('name') or CATS[cat_id][0] + ' (nom yozilmagan)'}")
    lines.append(f"Kategoriya: {CATS[cat_id][0]}" + ("" if d.get("cat") else " (avtomatik)"))
    if d.get("cny"):
        lines.append(f"Xitoy narxi: ¥{d['cny']:g} · og'irlik {p['grams'] / 1000:g} kg" + (" (standart)" if p["auto_kg"] else ""))
        lines.append(f"Tannarx (landed): {money(p['landed'])}")
    else:
        lines.append("Xitoy narxi: ❗ yozilmagan (masalan: ¥45)")
    if p["sale"]:
        extra = f" · foyda ≈ {money(p['sale'] - p['landed'])}" if p["landed"] else ""
        lines.append(f"Sotuv narxi: {money(p['sale'])}" + (" (qo'lda)" if d.get("price") else "") + extra)
    if d.get("sizes"):
        lines.append("Razmerlar: " + ", ".join(d["sizes"]))
    elif cat_id in SIZED_CATS:
        lines.append("Razmerlar: yozilmagan → mijoz razmer va rangni o'zi yozadi")
    lines.append(f"📷 Rasmlar: {len(d['img'])}" + ("" if d["img"] else " ❗ kamida 1 ta rasm kerak"))
    if d.get("url"):
        gid = goods_id(d["url"])
        lines.append("🔗 Manba: " + d["url"][:70] + ("…" if len(d["url"]) > 70 else "") + (f" (ID {gid})" if gid else ""))
    lines += ["", "O'zgartirish uchun yangi xabar yuboring: ¥52 · 0.6kg · r: S-XL · =199000 · yangi nom."]
    return "\n".join(lines)


def draft_kb(d):
    cur = d.get("cat") or "kiyim"
    btns = [{"text": ("• " if k == cur else "") + v[3], "callback_data": f"d:cat:{k}"} for k, v in CATS.items()]
    return {"inline_keyboard": [btns[:4], btns[4:],
                                [{"text": "✅ Katalogga qo'shish", "callback_data": "d:ok"},
                                 {"text": "🗑 Bekor", "callback_data": "d:no"}]]}


def draft_show(chat_id, uid):
    d = draft_load(uid)
    if d.get("card"):
        api("deleteMessage", chat_id=chat_id, message_id=int(d["card"]))
    r = api("sendMessage", chat_id=chat_id, text=draft_text(d), reply_markup=draft_kb(d),
            link_preview_options={"is_disabled": True})
    if r.get("ok"):
        draft_save(uid, {"card": r["result"]["message_id"]})


def best_photo(sizes):
    ok = [p for p in sizes if max(p.get("width", 0), p.get("height", 0)) <= 1280]
    return (ok or sizes)[-1]["file_id"]


def admin_message(m, uid, chat_id, text):
    """Admin qoralama oqimi. True qaytarsa xabar qayta ishlangan."""
    if m.get("photo"):
        kv(["RPUSH", f"d:{uid}:img", best_photo(m["photo"])], ["EXPIRE", f"d:{uid}:img", 172800])
        if m.get("caption"):
            draft_save(uid, parse_caption(m["caption"]))
        mg = m.get("media_group_id")
        if mg:
            # albomdagi faqat bitta xabar kartochka chiqaradi, qolgan rasmlar yetib kelishini kutib
            if not kv(["SET", f"d:{uid}:mg:{mg}", 1, "NX", "EX", 120])[0]:
                return True
            time.sleep(2.5)
        draft_show(chat_id, uid)
        return True
    if text and not text.startswith("/"):
        fields = parse_caption(text)
        if not fields:
            api("sendMessage", chat_id=chat_id, text="Tushunmadim. Tovar qo'shish uchun: rasmlar + havola + ¥narx. Yordam: /yordam")
            return True
        draft_save(uid, fields)
        draft_show(chat_id, uid)
        return True
    return False


HELP = """📦 PDD'dan tovar qo'shish

1. PDD ilovasida tovarni oching → 分享 → 复制链接 (havolani nusxalang).
2. Botga 1–6 ta rasm (skrinshot) yuboring. Izohga havola va narxni yozing, masalan:
   https://mobile.yangkeduo.com/... ¥45 Ipak pijama r: S-XL
3. Bot sotuv narxini o'zi hisoblaydi va kartochka chiqaradi.
4. Kategoriyani tekshiring va «✅ Katalogga qo'shish» bosing — tovar darhol Mini App'da chiqadi.

Izohda tushunadigan narsalar:
• ¥45 yoki 45元 — Xitoy narxi
• 0.6kg yoki 600g — og'irlik (yozilmasa kategoriya bo'yicha olinadi)
• r: S-XL yoki r: 36-41 — razmerlar
• =199000 — sotuv narxini qo'lda belgilash
• qolgan so'zlar — tovar nomi

Buyruqlar:
/tovarlar — oxirgi qo'shilganlar
/del KOD — tovarni katalogdan olib tashlash
/bekor — qoralamani tozalash
/kurs — kurslarni ko'rish; /kurs 12000 1810 — USD va CNY kursini o'zgartirish"""


def admin_command(chat_id, uid, text):
    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    arg = arg.strip()
    if cmd in ("/yordam", "/help", "/qoshish"):
        api("sendMessage", chat_id=chat_id, text=HELP, link_preview_options={"is_disabled": True})
    elif cmd == "/bekor":
        kv(["DEL", f"d:{uid}", f"d:{uid}:img"])
        api("sendMessage", chat_id=chat_id, text="Qoralama tozalandi. Yangi tovar uchun rasm yuboring.")
    elif cmd == "/tovarlar":
        items = [json.loads(v) for v in pairs(kv(["HGETALL", "prod"])[0]).values()]
        items.sort(key=lambda p: p.get("t", 0), reverse=True)
        if not items:
            api("sendMessage", chat_id=chat_id, text="Bot orqali qo'shilgan tovar hali yo'q. /yordam")
            return True
        lines = [f"Bot orqali qo'shilgan: {len(items)} ta. Oxirgilari:"]
        lines += [f"{p['id']} · {p['name']} · {money(p['price'])}" for p in items[:20]]
        lines.append("\nO'chirish: /del KOD")
        api("sendMessage", chat_id=chat_id, text="\n".join(lines))
    elif cmd == "/del":
        pid = arg.lower()
        if not re.fullmatch(r"[a-z0-9]{2,16}", pid):
            api("sendMessage", chat_id=chat_id, text="Masalan: /del n5k2xq (kod tovar sahifasida «Kod» qatorida turadi)")
            return True
        removed, _ = kv(["HDEL", "prod", pid], ["HDEL", "src", pid])
        if not removed:
            kv(["SADD", "hidden", pid])
        api("sendMessage", chat_id=chat_id, text=f"{pid.upper()} katalogdan olib tashlandi.")
    elif cmd == "/kurs":
        nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", arg)]
        if len(nums) >= 2:
            kv(["HSET", "cfg", "usd", nums[0], "cny", nums[1]])
        rt = rates()
        api("sendMessage", chat_id=chat_id,
            text=f"Kurs: 1 USD = {rt['usd']:g} so'm, 1 CNY = {rt['cny']:g} so'm.\nKargo ${CARGO_USD_PER_KG}/kg, komissiya {int(AGENT_FEE * 100)}%, bufer {int(BUFFER * 100)}%.\n"
                 "O'zgartirish: /kurs 12000 1810\n(Faqat yangi qo'shiladigan tovarlarga ta'sir qiladi.)")
    else:
        return False
    return True


def draft_callback(c, uid):
    msg = c.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    parts = c["data"].split(":")
    if parts[1] == "cat" and len(parts) == 3 and parts[2] in CATS:
        draft_save(uid, {"cat": parts[2]})
        d = draft_load(uid)
        api("editMessageText", chat_id=chat_id, message_id=msg.get("message_id"), text=draft_text(d),
            reply_markup=draft_kb(d), link_preview_options={"is_disabled": True})
        api("answerCallbackQuery", callback_query_id=c["id"], text=CATS[parts[2]][0])
    elif parts[1] == "no":
        kv(["DEL", f"d:{uid}", f"d:{uid}:img"])
        api("editMessageText", chat_id=chat_id, message_id=msg.get("message_id"), text="🗑 Qoralama bekor qilindi.")
        api("answerCallbackQuery", callback_query_id=c["id"])
    elif parts[1] == "ok":
        d = draft_load(uid)
        p = draft_price(d)
        if not d["img"]:
            api("answerCallbackQuery", callback_query_id=c["id"], show_alert=True, text="Kamida 1 ta rasm yuboring.")
            return
        if not p["sale"]:
            api("answerCallbackQuery", callback_query_id=c["id"], show_alert=True,
                text="Narx yo'q. Xitoy narxini yozing (masalan ¥45) yoki sotuv narxini (=199000).")
            return
        cat = d.get("cat") or "kiyim"
        pid = "n" + format(int(time.time()), "x")[-6:] + random.choice("abcdefghjkmnpqrstuvwxyz")
        prod = {"id": pid, "cat": cat, "name": d.get("name") or CATS[cat][0], "price": p["sale"],
                "img": d["img"][:8], "d": time.strftime("%Y-%m-%d", time.gmtime(time.time() + 5 * 3600)),
                "t": int(time.time()), "new": 1}
        if d.get("sizes"):
            prod["sizes"] = d["sizes"]
        elif cat in SIZED_CATS:
            prod["ask"] = 1
        source = {"url": d.get("url", ""), "cny": d.get("cny"), "kg": p["grams"] / 1000, "landed": p["landed"]}
        kv(["HSET", "prod", pid, json.dumps(prod, ensure_ascii=False)],
           ["HSET", "src", pid, json.dumps(source, ensure_ascii=False)],
           ["DEL", f"d:{uid}", f"d:{uid}:img"])
        api("editMessageText", chat_id=chat_id, message_id=msg.get("message_id"),
            link_preview_options={"is_disabled": True},
            text=(f"✅ Katalogga qo'shildi\n\n{prod['name']} — {money(prod['price'])}\nKod: {pid.upper()} · "
                  f"{CATS[cat][0]} · {len(prod['img'])} ta rasm\n\nOlib tashlash: /del {pid}\nKeyingi tovar uchun rasm yuboring."))
        api("answerCallbackQuery", callback_query_id=c["id"], text="Katalogga qo'shildi ✓")


def source_lines(items):
    ids = [it["id"] for it in items]
    try:
        found = kv(["HMGET", "src", *ids])[0] or []
    except Exception:  # noqa: BLE001
        return ""
    out = []
    for k, (it, raw) in enumerate(zip(items, found), 1):
        if raw:
            s = json.loads(raw)
            if s.get("url"):
                out.append(f"{k}. {s['url']}" + (f" (¥{s['cny']:g})" if s.get("cny") else ""))
    return ("\n\n🔗 Xitoydan olish:\n" + "\n".join(out)) if out else ""


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


def card_text(n, status, o, user, links="") -> str:
    emoji, label = STATUSES[status]
    who = f"@{user.get('username')}" if user.get("username") else f"id {user.get('id')}"
    return (f"Buyurtma #{n} · {emoji} {label}\n\n{items_lines(o['items'])}\n\n"
            f"Tovarlar: {money(o['sub'])}\nYetkazish: {money(o['del'])}\nJami: {money(o['tot'])}\n"
            f"Oldindan (50%): {money(o['pre'])}\n\n"
            f"👤 {o['name']} · {who}\n📞 {o['phone']}\n📍 {o['region']}, {o['address']}\n💳 {o['pay']}"
            + (f"\n📝 {o['note']}" if o["note"] else "") + links)


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
        links = source_lines(o["items"])
        sent = api("sendMessage", chat_id=ADMIN_CHAT_ID, text=card_text("…", "new", o, user, links),
                   link_preview_options={"is_disabled": True})
        n = sent.get("result", {}).get("message_id", "?")
        if sent.get("ok"):
            api("editMessageText", chat_id=ADMIN_CHAT_ID, message_id=n, text=card_text(n, "new", o, user, links),
                reply_markup=status_kb("new", uid, o["pre"]), link_preview_options={"is_disabled": True})
        api("sendMessage", chat_id=chat_id, parse_mode="HTML", reply_markup=main_keyboard(uid),
            text=(f"✅ Buyurtma <b>#{n}</b> qabul qilindi!\n\n{html.escape(items_lines(o['items']))}\n\n"
                  f"Jami: <b>{money(o['tot'])}</b>\nOldindan to'lov (50%): <b>{money(o['pre'])}</b>\n\n"
                  "Admin tez orada buyurtmani tasdiqlab, to'lov ma'lumotini yuboradi."))
        return
    text = (m.get("text") or "").strip()
    if is_admin(uid) and m["chat"].get("type") == "private":
        try:
            if text.startswith("/") and not text.startswith(("/start", "/id")) and admin_command(chat_id, uid, text):
                return
            if admin_message(m, uid, chat_id, text):
                return
        except KVError as e:
            api("sendMessage", chat_id=chat_id, text=f"Baza bilan muammo: {e}")
            return
    if not is_admin(uid) and m["chat"].get("type") == "private" and not text.startswith("/"):
        if m.get("photo") or m.get("document") or text:
            api("forwardMessage", chat_id=ADMIN_CHAT_ID, from_chat_id=chat_id, message_id=m["message_id"])
            api("sendMessage", chat_id=ADMIN_CHAT_ID, text=f"↑ Mijozdan: id {uid}"
                + (f" @{user['username']}" if user.get("username") else ""))
            api("sendMessage", chat_id=chat_id, text="Xabaringiz adminga yetkazildi. Tez orada javob beramiz.")
        return
    if text.startswith("/start"):
        api("sendMessage", chat_id=chat_id, parse_mode="HTML", reply_markup=main_keyboard(uid),
            text=(f"Assalomu alaykum! <b>{STORE_NAME}</b> ga xush kelibsiz.\n\n"
                  "Pastdagi <b>🛍 Katalogni ochish</b> tugmasini bosing: tovarni tanlang, razmerni belgilang va "
                  "buyurtma bering. Buyurtma raqami shu yerga keladi.")
            + ("\n\n<b>Admin:</b> PDD'dan tovar qo'shish uchun rasm + havola + ¥narx yuboring. Batafsil: /yordam"
               if is_admin(uid) else ""))
    elif text.startswith("/id"):
        api("sendMessage", chat_id=chat_id, text=f"Sizning ID: {uid}\nShu chat ID: {chat_id}")


def on_callback(c):
    uid = c["from"]["id"]
    if not is_admin(uid):
        api("answerCallbackQuery", callback_query_id=c["id"], text="Faqat admin uchun", show_alert=True)
        return
    if c.get("data", "").startswith("d:"):
        try:
            draft_callback(c, uid)
        except KVError as e:
            api("answerCallbackQuery", callback_query_id=c["id"], text=f"Baza bilan muammo: {e}", show_alert=True)
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
        reply_markup=status_kb(st, cust, pre), link_preview_options={"is_disabled": True})
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
