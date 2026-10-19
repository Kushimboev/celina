# Celina Store — o'zgarishlar jurnali

Yangi yozuv tepaga qo'shiladi. Format: sana · nima · nega · fayllar · sinov.
Umumiy rasm uchun: `docs/LOYIHA_XARITASI.md`.

---

## 2026-10-19 (kechqurun) — Loyiha xaritasi va admin buyruqlari menyusi
- `docs/LOYIHA_XARITASI.md` (yagona manba), `docs/OZGARISHLAR.md`, `CLAUDE.md`, `AGENTS.md` qo'shildi — har qanday AI sessiya loyihani shu yerdan davom ettira olishi uchun.
- Botda adminga ko'rinadigan buyruqlar menyusi o'rnatildi (`setMyCommands`, scope = admin chat): /start, /yordam, /tovarlar, /del, /bekor, /kurs, /id. Mijozlar faqat /start ko'radi.
- Nusxasi Claude "Celina store" loyihasiga yozildi: `Celina/LOYIHA_XARITASI.md`, `Celina/OZGARISHLAR.md`.

## 2026-10-19 — 1-bosqich: PDD/Taobao/1688 tovarlarini bot orqali qo'shish (commit f2146a3)
- Nega: egasi PDD tovarlarini to'g'ridan-to'g'ri botga joylashni so'radi. Rasmiy PDD API (多多进宝) Xitoy akkaunti talab qiladi, mobil saytdan scraping login/cookie talab qiladi va beqaror → saralangan yarim-avtomatik yo'l tanlandi.
- Vercel Storage → Upstash Redis ("upstash-kv-green-car", Free) ulandi (egasi o'zi bosdi; KV_* env avtomatik).
- `api/webhook.py`: admin rasm(lar) + izoh (havola, ¥narx, kg, `r:` razmer, `=` qo'lda narx, nom) → qoralama kartochka (tannarx, narx, foyda, kategoriya tugmalari) → ✅ → Redis `prod`/`src`. Albom uchun NX qulf + 2.5 s kutish. Buyruqlar /yordam, /tovarlar, /del, /bekor, /kurs. Buyurtma kartochkasida "🔗 Xitoydan olish" (manba havolasi + ¥). Mijozning botga yozgan xabari/rasmi adminga forward.
- `api/products.py` (yangi): `GET /api/products` → bot tovarlari + `hidden`.
- `index.html`: /api/products birlashtiriladi (yangi tovarlar boshida), "Yangi" chip va belgi, `hidden` filtrlanadi.
- Sinov: mahalliy mock bilan to'liq oqim; serverda soxta admin update bilan "SINOV pijama" (¥45, S–L → 319 000 so'm) qo'shildi va `/del` bilan o'chirildi; `/api/products` → `db: true`. Playwright bilan Mini App birlashtirish tekshirildi.

## 2026-10-19 — Bot 24/7 serverda (Vercel webhook)
- Mac'dagi aiogram polling bot o'rniga `api/webhook.py` (stdlib, bazasiz): buyurtma raqami = admin kartochkasining message_id, status `callback_data` da. Webhook secret = sha256("celina:"+token)[:48].
- `api/img.py`: Telegram file_id → rasm proksi (token serverda).
- `BOT_TOKEN` Vercel'ga egasi tomonidan kiritildi; webhook o'rnatildi; noto'g'ri secret → 403 tekshirildi.
- Mac'dagi `~/Desktop/celina-bot` endi ishlatilmaydi.

## 2026-10-19 — Haqiqiy katalog: kanal tarixidan 548 tovar
- Manba: Desktop'dagi "Celina telegram history" (kanal guruhi eksporti). Narxli postlar ajratildi, rasmlar Telegram'ga yuklanib file_id olindi (`sendMediaGroup` → o'chirish).
- 8 kategoriya, 177 tovarda razmer ro'yxati, qolgan kiyimlarda `ask:1`; 27 tovar "Ko'p so'ralgan" ("Zakaslarim"dagi buyurtmalar bilan vaqt ±120 s va narx bo'yicha moslangan).
- `products.json` GitHub'ga yuklandi (har qatorda bitta obyekt), SHA bilan tekshirildi.

## 2026-10-19 — Mini App va hosting
- Telegram Mini App (`index.html`): katalog, qidiruv, kategoriyalar, tovar sahifasi (galereya, razmer jadvali), savatcha, rasmiylashtirish, `sendData` buyurtma, `#admin` narx kalkulyatori, Telegram tema/BackButton/haptic.
- Tuzatish: Telegram muhitini aniqlash `initData` bo'yicha emas, `platform !== "unknown"` bo'yicha (reply-keyboard'dan ochilganda initData bo'sh) — busiz buyurtma botga yetmasdi.
- Hosting: GitHub Pages shgen.me domeniga yo'naltirib 404 berdi → Vercel (loyiha `celina`, https://celina-red.vercel.app).
- Bot @Celina_store_bot: profil to'ldirildi, /start klaviaturasi.

## 2026-09-23 — Telegram tarixi tahlili
- `claude/celina-telegram-tahlil-2026-09.md` (Claude loyihasida): ~518 tovar posti, ~40–50 dona/oy sotuv, xulosa — tor joy trafik va ishonch.

## 2026-06-26 — Strategik reja
- `Velora/Velora_Strategik_Reja.docx/.pdf` (Claude loyihasida): landed cost modeli, ×2.5 qoidasi, 90 kunlik reja, KPI, risklar.
