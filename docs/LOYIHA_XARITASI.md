# Celina Store — loyiha xaritasi (yagona manba)

> **AI / yangi sessiya uchun:** loyiha bo'yicha har qanday ishni boshlashdan oldin shu faylni to'liq o'qing.
> Ish tugagach **shu faylni va `docs/OZGARISHLAR.md` ni yangilang** (qoidalar — 13-bo'lim).
> English summary for other agents: this is the single source of truth for the Celina Store project
> (China→Uzbekistan resale shop: Telegram bot + Mini App on Vercel, Upstash Redis). Read fully before
> acting; update this file and `docs/OZGARISHLAR.md` after every change. User speaks Uzbek.

Oxirgi yangilanish: **2026-10-19** · Yangilagan: Claude (Cowork sessiyasi)

---

## 1. Biznes qisqacha

| | |
|---|---|
| Egasi | Shavkat Qushimboyev (admin, qarorlar uning). Brend imzosi "by Marxabo" (bot nomi Celina_by_Marxabo). |
| Do'kon nomi | **Celina Store** (avval "Velora" deb rejalashtirilgan — nom band edi) |
| Model | Xitoydan (Pinduoduo asosan, Taobao/1688) qayta sotish. **Pre-order**: mijoz 50% oldindan to'laydi → tovar Xitoyda olinadi → 10–14 kunda Toshkentga → yetkaziladi |
| Nisha | Ayollar kiyimi, pijama, sumka; amalda oyoq kiyim va bolalar kiyimi ham ko'p |
| Kanallar | Telegram kanal "CELINA STORE🛍️💗" + muhokama guruhi; Telegram bot **@Celina_store_bot**; Instagram (hali faol emas) |
| Logistika | Buyer-agent PDD'dan oladi, konsolidatsiya, kargo **$5.5/kg**, Toshkentga 7–15 kun |
| Kapital | < $500 — shuning uchun zaxirasiz, pre-order |

### Hozirgi holat (raqamlar, 2026-09 tahlili)
- Kanalda ~518 narxli tovar posti (26.06–23.09.2026), mediana narx ~110 000 so'm.
- Sotuv: ~40–50 dona/oy, mijozlarning katta qismi tanishlar. Post faolligi pasaygan.
- **Asosiy xulosa: tor joy assortiment emas — trafik va ishonch.**
- Og'ir tovarlar (sumka, oyoq kiyim) eski narxlarda tannarxdan arzon sotilgan (sumka landed ~132k, sotuv 105–110k).

Batafsil: Claude loyihasidagi `Velora/Velora_Strategik_Reja.docx` va `claude/celina-telegram-tahlil-2026-09.md`.

---

## 2. Asosiy maqsad va strategiya

**Maqsad:** Celina'ni tanishlar doirasidan chiqib, begona mijozlar ham ishonib buyurtma beradigan,
foydali (marja ≥ 55%) va kam qo'l mehnati talab qiladigan onlayn do'konga aylantirish.

Strategik tamoyillar:
1. **Har narx — True Landed Cost asosida** (5-bo'lim). Hech qachon ×2.0 dan past sotmaslik; standart ×2.5.
2. **Yengil, yuqori marjali tovarlarga fokus** (pijama, ko'ylak, aksessuar). Og'ir tovar faqat to'g'ri narxda.
3. **Pre-order → aralash model:** eng ko'p sotilgan 5–10 SKU isbotlangach kichik zaxira ("Tayyor, 1–2 kun").
4. **Saralangan katalog**, PDD'ning to'liq nusxasi emas (narx/mavjudlik tez o'zgaradi, razmer muammosi).
5. **Ishonch:** razmer jadvali (sm), mato tarkibi, aniq to'lov va muddat, mijoz sharhlari, buyurtma raqami va status xabarlari.
6. **Avtomatlashtirish:** narx hisoblash, buyurtma qabul qilish, status xabarlari — bot zimmasida; Xitoydan sotib olish — qo'lda (admin).

### KPI (90 kunlik maqsadlar)
| Ko'rsatkich | Maqsad |
|---|---|
| O'rtacha marja | ≥ 55% |
| Qaytarish/shikoyat | < 5% |
| Takroriy xaridor | ≥ 25% |
| Deadstock ulushi | < 10% |
| O'rtacha chek | har oy o'sishi |
| Begona (tanish bo'lmagan) mijozlar ulushi | o'sishi — asosiy o'sish ko'rsatkichi |

---

## 3. Tizim arxitekturasi

```
 Mijoz (Telegram)
   │  /start → "🛍 Katalogni ochish" (reply-keyboard web_app tugmasi)
   ▼
 Mini App  https://celina-red.vercel.app/   (index.html, statik)
   │  o'qiydi: products.json (548 kanal tovari) + /api/products (bot orqali qo'shilganlar)
   │  rasmlar: /api/img?f=<telegram file_id>
   │  buyurtma: Telegram.WebApp.sendData(JSON)  → bot chatiga web_app_data bo'lib keladi
   ▼
 Telegram Bot API ──webhook──▶ /api/webhook  (Vercel serverless, Python, faqat stdlib)
                                 │  admin kartochka → ADMIN_CHAT_ID (status tugmalari)
                                 │  mijozga status xabarlari
                                 │  admin: PDD tovar qo'shish (qoralama → ✅)
                                 ▼
                         Upstash Redis (Vercel Storage: "upstash-kv-green-car")
```

| Komponent | Qayerda | Izoh |
|---|---|---|
| Kod | GitHub **Kushimboev/celina** (branch `main`, hozircha **public**) | `main` ga push → Vercel avtomatik deploy |
| Hosting | Vercel, akkaunt `qushimboyevshavkatjon-1590s-projects`, loyiha **celina**, Hobby (bepul) | URL: https://celina-red.vercel.app |
| Bot | @Celina_store_bot (ko'rinadigan nomi "Celina_by_Marxabo"), bot id 8872939670 | Webhook: `https://celina-red.vercel.app/api/webhook`, allowed_updates: message, callback_query |
| Admin | Telegram user id **500336914** (Shavkat) | `ADMIN_IDS`, `ADMIN_CHAT_ID` |
| Baza | Upstash Redis (Vercel Marketplace, Free) | Kalitlar — 6-bo'lim |
| Tovar rasmlari | Telegram serverlarida (file_id) | `/api/img` proksi orqali, token serverda qoladi |
| Eski lokal bot | Mac: `~/Desktop/celina-bot/` (aiogram polling, `bot.py`, `orders.db`) | **ISHLATILMAYDI.** Webhook yoqilgan, uni ishga tushirmang (409 xato beradi). Faqat `.env` dagi token uchun saqlanadi |
| Preview artifact | https://claude.ai/artifact/YQptvnwCZHpCZbiSpUPmh5 | Eski demo versiya, faqat ko'rish uchun |

---

## 4. Fayllar xaritasi (repo)

| Fayl | Vazifasi |
|---|---|
| `index.html` | Butun Mini App (HTML+CSS+JS bitta faylda). Boshida `CONFIG` (kurs, kargo, to'lov ulushi, yetkazish narxi), `CATEGORIES` (koeffitsient, standart og'irlik), `SIZE_CHARTS`. Ko'rinishlar: katalog, tovar, savatcha, rasmiylashtirish, "done", `#admin` (narx kalkulyatori) |
| `products.json` | Kanal tarixidan yig'ilgan 548 tovar (har qatorda bitta obyekt). Statik |
| `api/webhook.py` | Telegram bot: buyurtma qabul qilish, status tugmalari, admin tovar qo'shish, buyruqlar, mijoz xabarlarini adminga yo'naltirish |
| `api/products.py` | `GET /api/products` → `{items, hidden, db}` Redis'dan (manba havolalarisiz) |
| `api/img.py` | `GET /api/img?f=<file_id>` → Telegram'dan rasmni oqim bilan beradi (1 yil kesh) |
| `CLAUDE.md`, `AGENTS.md` | AI agentlar uchun kirish nuqtasi → shu faylga yo'naltiradi |
| `docs/LOYIHA_XARITASI.md` | Shu fayl — yagona manba |
| `docs/OZGARISHLAR.md` | Sana bo'yicha o'zgarishlar jurnali |

---

## 5. Narx formulasi (True Landed Cost)

```
goods  = CNY × kurs_CNY
cargo  = kg × 5.5 $ × kurs_USD
fee    = goods × 8%            (agent/karta komissiyasi)
landed = (goods + cargo + fee + 2000 qadoqlash) × 1.07   (brak/deadstock buferi)
sotuv  = landed × koeffitsient → yuqoriga ...9 000 ga yaxlitlanadi (masalan 313 671 → 319 000)
```

| Kategoriya (id) | Koeff. | Standart og'irlik |
|---|---|---|
| oyoq | 2.3 | 600 g |
| bolalar | 2.5 | 300 g |
| pijama | 2.5 | 420 g |
| kiyim | 2.5 | 450 g |
| sumka | 2.3 | 550 g |
| aksessuar | 3.0 | 150 g |
| kosmetika | 2.5 | 200 g |
| uy | 2.5 | 400 g |

Kurslar: USD 11 963, CNY 1 803 so'm (MB, oktyabr 2026). Botda `/kurs 12000 1810` bilan Redis `cfg` ga yoziladi
(faqat bot orqali yangi qo'shiladigan tovarlarga ta'sir qiladi).

⚠️ **Formula ikki joyda takrorlangan:** `index.html` (`CONFIG`, `CATEGORIES`, `calc`, `roundPsy`) va
`api/webhook.py` (`RATES`, `CARGO_USD_PER_KG`…, `CATS`, `calc`, `round_psy`). Birini o'zgartirsangiz, ikkinchisini ham.
Kanal tovarlarining narxi (`products.json` dagi `price`) kanaldagi asl narx — formula bilan qayta hisoblanmagan.

---

## 6. Ma'lumot modellari

### products.json / /api/products tovari
```json
{"id":"c6058","cat":"kosmetika","name":"Kosmetika №38","price":29000,
 "img":["<telegram file_id>", "..."], "pop":1, "d":"2026-09-06",
 "sizes":["S","M"], "ask":1, "new":1, "t":1792418526}
```
- `id`: kanal tovarlari `c…`, bot orqali qo'shilganlar `n…`
- `ask:1` — razmer/rangni mijoz o'zi yozadi; `pop:1` — "Ko'p so'ralgan"; `new:1` — bot orqali qo'shilgan ("Yangi" belgisi)
- Mini App: bot tovarlari ro'yxat boshida; `hidden` dagi id'lar ko'rsatilmaydi

### Redis kalitlari (Upstash)
| Kalit | Turi | Mazmuni |
|---|---|---|
| `prod` | hash | id → tovar JSON (ommaviy) |
| `src` | hash | id → `{url, cny, kg, landed}` — **faqat admin** (buyurtma kartochkasida chiqadi) |
| `hidden` | set | `/del` bilan yashirilgan kanal tovarlari id'lari |
| `cfg` | hash | `usd`, `cny` kurslari |
| `d:<uid>` | hash | admin qoralamasi: url, cny, kg, cat, name, sizes, price, card (48 soat TTL) |
| `d:<uid>:img` | list | qoralama rasmlari (file_id) |
| `d:<uid>:mg:<media_group_id>` | string | albom uchun bitta kartochka chiqarish qulfi (120 s) |

### Buyurtma (Mini App → bot, `sendData`)
```json
{"v":1,"i":[{"id","n","s","c","q","p"}],"cu":{"n","ph","r","a","pay","note"},"sub","del","tot","pre"}
```
Server jami summani qayta hisoblaydi, yetkazish ≤ 200 000 bilan cheklanadi, oldindan to'lov = 50%.
**Buyurtma raqami = admin kartochkasining Telegram message_id** (#1842 kabi). Buyurtma ma'lumoti
alohida bazada emas — admin kartochkasining matnida. Kartochkalarni o'chirmang.

### Status tugmalari
`callback_data = "s:<status>:<mijoz_id>:<oldindan_to'lov>"`; statuslar: new → confirmed → paid → ordered →
arrived → delivered | cancelled. Har bosilganda kartochka 1-qatori yangilanadi va mijozga xabar ketadi
(`confirmed` xabarida `PAYMENT_TEXT`). Qoralama tugmalari: `d:cat:<id>`, `d:ok`, `d:no`.

---

## 7. Foydalanuvchi oqimlari

**Mijoz:** /start → Katalog → tovar (razmer, rang yoki "Razmer va rang" maydoni) → savatcha → ism, telefon,
viloyat, manzil, to'lov usuli → yuborish → botdan "✅ Buyurtma #N qabul qilindi" → status xabarlari.
Mijoz botga yozgan matn/rasm (masalan to'lov cheki) adminga forward bo'ladi.
Telegram'dan tashqarida ochilsa — buyurtma matni ko'rsatiladi, mijoz uni adminga o'zi yuboradi.

**Admin — PDD'dan tovar qo'shish:** PDD'da 分享 → 复制链接 → botga 1–6 rasm + izoh:
`<havola> ¥45 Ipak pijama r: S-XL` (qo'shimcha: `0.6kg`, `=199000` qo'lda narx) → qoralama kartochka
(tannarx, narx, foyda) → kategoriya tugmasi → **✅ Katalogga qo'shish** → ~1 daqiqada Mini App'da.
Buyurtma kelganda kartochkada "🔗 Xitoydan olish" havolasi chiqadi → admin PDD'da qo'lda sotib oladi.

**Admin buyruqlari** (faqat adminga ko'rinadi): `/yordam`, `/tovarlar`, `/del KOD`, `/bekor`, `/kurs USD CNY`, `/id`.
Mijozlar uchun: `/start`.

---

## 8. Deploy va operatsiyalar

- **Deploy:** `main` branch'ga push → Vercel o'zi build qiladi (~1 daqiqa). Build sozlamasi yo'q (statik + `api/*.py`).
- **Muhit o'zgaruvchilari (Vercel → celina → Settings → Environment Variables):**
  `BOT_TOKEN` (secret), `WEBAPP_URL` (default celina-red.vercel.app), `ADMIN_CHAT_ID`, `ADMIN_IDS`,
  `STORE_NAME`, `PAYMENT_TEXT` (**hali qo'yilmagan** — default umumiy matn), `KV_REST_API_URL`,
  `KV_REST_API_TOKEN`, `KV_REST_API_READ_ONLY_TOKEN` (Upstash ulanganda Vercel o'zi qo'shgan).
  O'zgaruvchi o'zgarsa — **Redeploy** kerak.
- **Webhook secret:** `sha256("celina:" + BOT_TOKEN)[:48]`, sarlavha `X-Telegram-Bot-Api-Secret-Token`. Noto'g'ri bo'lsa 403.
- **Webhook qayta o'rnatish:** `setWebhook?url=https://celina-red.vercel.app/api/webhook&secret_token=<secret>&allowed_updates=["message","callback_query"]`
- **Tekshiruv:** `GET /api/webhook` → "Celina bot ishlayapti"; `GET /api/products` → `"db": true`; `getWebhookInfo` → pending 0, xatosiz.
- **Sinov usuli:** webhook'ga to'g'ri secret bilan soxta update POST qilish (admin id 500336914) — serverda to'liq oqim sinaladi.
  Mahalliy sinov: `api/webhook.py` ni import qilib `kv` va `api` ni mock qilish.
- **Sirlar qoidasi:** bot tokeni hech qachon kodga, hujjatga yoki chatga yozilmaydi. Joyi: Vercel env (secret) va Mac'dagi `~/Desktop/celina-bot/.env` (chmod 600).
  AI token/parol/karta raqamini web formaga o'zi kiritmaydi — buni egasi qiladi.

---

## 9. Ma'lum cheklovlar va xavflar

- PDD'ni to'liq avtomatik ulash amalda mumkin emas: rasmiy API (多多进宝) Xitoy akkaunti/real-name talab qiladi; mobil sayt login va cookie talab qiladi. Yo'l — pullik vositachi API (OTCommerce va b.) — 2-bosqich.
- Bot orqali qo'shilgan narx qo'shilgan paytdagi kurs bilan qotadi; PDD narxi/mavjudligi o'zgarsa xabar kelmaydi → sotib olishdan oldin havolani tekshirish.
- Kanal tovarlari nomlari umumiy ("Oyoq kiyim №95") — chiroyli nomlar kerak.
- Mini App `adminUsername: "celina_store_admin"` (Telegram'dan tashqarida buyurtma uchun) — bunday username borligi tekshirilmagan.
- Repo public — biznes ma'lumotlari ko'rinadi; private qilish tavsiya etiladi (Vercel Hobby private repo bilan ishlaydi).
- `/api/products` CDN keshi 15 s (+60 s stale) — yangi tovar 1 daqiqagacha kechikib chiqishi mumkin.
- Razmer: Xitoy razmerlari odatda bitta kichik; umumiy jadvallar taxminiy.
- Temu O'zbekistonda bloklangan (raqobat omili). Jismoniy shaxs bojsiz limiti $200/oy (2026) — kargo bilan tekshirish kerak.

---

## 10. Yo'l xaritasi

| Bosqich | Holat |
|---|---|
| Strategik reja, landed cost modeli, narx qoidalari | ✅ 2026-06 |
| Telegram tarixi tahlili (sotuv, kategoriyalar, muammo) | ✅ 2026-09 |
| Mini App (katalog, savatcha, buyurtma, razmer jadvali, admin kalkulyator) | ✅ 2026-10-19 |
| Bot 24/7 (Vercel webhook), buyurtma raqami, status xabarlari | ✅ 2026-10-19 |
| Kanal tarixidan 548 haqiqiy tovar + rasmlar katalogda | ✅ 2026-10-19 |
| **1-bosqich PDD:** havola+rasm+¥narx → bot orqali katalogga, manba havolasi buyurtmada | ✅ 2026-10-19 |
| To'lov ma'lumoti (`PAYMENT_TEXT`) | ⏳ egasi qo'yadi |
| Haqiqiy mijoz bilan to'liq sinov (telefonda katalog → buyurtma → statuslar) | ⏳ |
| Kanal tovarlariga chiroyli nomlar, mato, razmer | 🔜 |
| Kanal postlariga "Botda buyurtma berish" havolasi, pinned post "Qanday buyurtma berish" | 🔜 |
| Buyurtmalar hisobi: oylik sotuv, marja, top SKU (Redis yoki Sheets) | 🔜 |
| Admin uchun narxni tahrirlash (`/narx KOD 199000`), tovar nomini o'zgartirish | 🔜 |
| Instagram ishga tushirish, kontent kalendari, mikro-bloggerlar | 🔜 |
| **2-bosqich PDD:** vositachi API — faqat havola bilan avtomatik nom/rasm/razmer/narx, kunlik narx tekshiruvi | 💡 1-bosqich natijasiga qarab |
| Top 5–10 SKU zaxira ("Tayyor, 1–2 kun", `stock:1`) | 💡 |
| Onlayn to'lov (Click/Payme API) | 💡 |
| To'liq mobil ilova | 💡 uzoq muddat |

---

## 11. Ochiq vazifalar

| Vazifa | Kim |
|---|---|
| Vercel'da `PAYMENT_TEXT` (Click/Payme raqami) qo'shib Redeploy | Shavkat |
| Mac'dagi eski bot Terminal oynasini yopish (Terminate) | Shavkat |
| Bot chatidagi "SINOV" kartochkalarini e'tiborsiz qoldirish / bekor qilish | Shavkat |
| Telefonda katalogni ochib, bitta haqiqiy PDD tovarini qo'shib ko'rish | Shavkat |
| Repo'ni private qilish yoki shunday qoldirish haqida qaror | Shavkat |
| `adminUsername` ni haqiqiy admin username bilan almashtirish | Claude (username ma'lum bo'lgach) |

---

## 12. Qarorlar jurnali

| Sana | Qaror | Sabab |
|---|---|---|
| 2026-06-26 | Pre-order modeli, sotuv = landed × 2.5 (min ×2.0) | Kapital < $500; og'ir tovarlarda zarar aniqlandi |
| 2026-09-24 | Do'kon nomi Celina Store; Telegram'da ishlash | — |
| 2026-10-19 | Telegram Mini App + bot (alohida sayt/ilova emas) | Mijozlar allaqachon Telegram'da, eng arzon va tez yo'l |
| 2026-10-19 | Hosting: Vercel (GitHub Pages emas) | Pages shgen.me custom domeniga yo'naltirib 404 berdi; Vercel serverless bot ham beradi |
| 2026-10-19 | Bot: webhook + serverless, Mac'dagi polling emas | 24/7, Mac o'chiq bo'lsa ham ishlaydi |
| 2026-10-19 | Buyurtma ma'lumoti admin kartochkasida (bazasiz) | Oddiylik; bepul |
| 2026-10-19 | Katalog = kanal tarixidagi 548 tovar | Haqiqiy tovarlar va rasmlar darhol |
| 2026-10-19 | PDD: saralangan qo'lda qo'shish (1-bosqich), to'liq ko'zgu emas | Rasmiy API yo'q, scraping beqaror; Telegram mijozi saralangan tovar oladi |
| 2026-10-19 | Baza: Upstash Redis (Vercel Storage, Free) | Bepul, serverless'ga mos, kalit kiritish shart emas |

---

## 13. Bu faylni yuritish qoidalari (har bir AI/sessiya uchun)

1. Ish boshlashdan oldin: shu faylni + `docs/OZGARISHLAR.md` ning oxirgi yozuvlarini o'qing. Kod bilan solishtiring — farq bo'lsa, kod haqiqat, faylni tuzating.
2. Har bir o'zgarishdan keyin (kod, sozlama, qaror, biznes raqami):
   - `docs/OZGARISHLAR.md` ga sana bilan yozuv qo'shing (nima, nega, qaysi fayllar, qanday sinaldi);
   - shu fayldagi tegishli bo'limni (arxitektura, model, yo'l xaritasi, ochiq vazifalar, qarorlar) yangilang va tepadagi sanani o'zgartiring;
   - commit xabari o'zbekcha, nima o'zgarganini aytsin.
3. Claude'dagi "Celina store" loyihasida shu faylning nusxasi bor (`Celina/LOYIHA_XARITASI.md`, `Celina/OZGARISHLAR.md`). Imkon bo'lsa uni ham yangilang; repo'dagi versiya asosiy.
4. Sirlarni (token, parol, karta raqami) hech qachon yozmang — faqat qayerda saqlanishini.
5. Narx formulasini o'zgartirsangiz — `index.html` va `api/webhook.py` ikkalasida.
6. Egasi bilan o'zbek tilida, qisqa va aniq, moliyaviy jadvallar bilan gaplashing.
