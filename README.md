# Shreeji SteelTubes – QR Chatbot (Python + Flask + MongoDB)

**Customers:** scan the QR code → the chatbot opens directly (no login). Their enquiry is saved with name + contact number.
**Admin:** only the admin logs in (navbar → *Admin Login*) to see enquiries, download **PDF**, export **CSV**, manage contacts / catalogue files / QR / admins.

## Setup
1. Install **Python 3.10+** and **MongoDB** (local MongoDB Community, or a free MongoDB Atlas cluster).
2. `python -m venv venv` → activate (`venv\Scripts\activate` on Windows, `source venv/bin/activate` on Linux/Mac)
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill it:
   - `MONGO_URI` (local `mongodb://localhost:27017` or your Atlas link)
   - `PUBLIC_URL` – address of your site (the QR code opens this)
   - `ADMIN_PHONE` / `ADMIN_PASSWORD` – first admin (saved in MongoDB on first run)
5. `python app.py`
6. Open http://localhost:5000 → chatbot with logo splash + watermark. Admin: http://localhost:5000/admin/login

## QR code
- Admin → **QR code** page: print the poster or download the image.
- The QR contains `QR_URL` (if set) or `PUBLIC_URL`. A phone cannot open `localhost`:
  - same Wi-Fi testing: `PUBLIC_URL=http://<your-PC-IP>:5000`
  - production: deploy on a server / domain (e.g. `gunicorn -w 2 -b 0.0.0.0:8000 app:app` behind nginx + HTTPS).

## Admin panel
- **Enquiries**: search / filter, change status, **⬇ Export CSV**, **⬇ Download PDF** (all, or per-enquiry PDF button).
- **Contacts**: department-wise contacts shown in bot option 3.
- **Catalog files**: upload catalogue, datasheet / weight chart, distribution certificate, awards.
- **Admins**: add more admins, disable, change your password.

## MongoDB collections (database `srj_bot`)
`admins` · `enquiries` · `customers` · `contacts` · `documents` · `chat_state` · `counters`

## Bot flow (fast - 3 steps)
Hi -> **one-time details in ONE message** (Name only) -> Welcome -> 1 Product Enquiry · 2 Catalog & Technical · 3 Contact details.

**Product Enquiry = 3 steps:**
1. **Product** - tap one (MS ERW / GI ERW / Square Hollow / Rectangular Hollow / Large Dia ERW / Spiral Welded)
2. **Specs - ONE message**, comma separated: `Size, Thickness, Length, Quantity` (optional at the end: `Grade, Standard`)
   e.g. `50 NB, 3.2 mm, 6 m, 5 MT, YST 240, IS 1239 (Part 1)`
3. **Delivery date - one tap** (Urgent / 1 week / 15 days / 1 month, or type DD-MM-YYYY, or Skip) -> enquiry is submitted.

Delivery location is taken from the customer's saved city; brand is left "Not specified". `back` = previous step, `menu` = cancel.
Date choices / examples can still be edited in `options.py`.

**Intro video / slides:** the intro video is a short **social-media engagement video** (how customers reach us directly): logo -> *Enquire in 3 Steps* (chat) -> *Follow Us on Facebook* -> *Talk to Us Directly* (call / email) -> *Get a Quote Online* -> *Connect With Us* -> closing logo. The swipeable company slides in the chat (About, Range, Stock, etc.) are separate images.
Edit `tools/make_intro_media.py` (`VIDEO` = video slides, `GALLERY` = chat slides) and run `python tools/make_intro_media.py` (needs `pip install pillow imageio-ffmpeg`). Add Instagram / LinkedIn / YouTube to `SOCIAL_EXTRA`, and your WhatsApp number to `WHATSAPP_NUMBER`, once you have them.

**Intro ad:** when the customer says *Hi* they see the company slides/video, then a **📍 Visit Us** card (address + Google Maps button + address + Google Maps button). Set `COMPANY_ADDRESS`, `MAPS_LINK` (exact pin link) and `COMPANY_PHONES` in `options.py`; if `COMPANY_PHONES` is empty, every department number saved in Admin → Contacts is used (departments with no number are hidden). Under *3 Contact Details* every department has its own **📞 direct call button** (tap = dial, no list/dropdown). It is not shown in the Visit Us card.

**Screen:** the web chat uses the whole device screen and is styled like WhatsApp (green header, beige wallpaper with logo watermark, green outgoing bubbles, quick-reply buttons, round send button).

## Smart replies, security & polish (latest update)
- **Free-text understanding (English + Hinglish):** customers can type `price of GI pipe`, `catalogue bhejo`, `address kya hai`, `jobs`, `documents`, `thanks` ... and the bot opens the right page. Rules are in `bot.py` -> `INTENTS` (add your own words there). Unknown text gets a friendly "I did not understand" hint + the menu, and `help` lists what can be typed.
- **Product cards:** "New here?" hint, animated *View details* on hover (laptop) / finger-touch (phone).
- **Documents:** the old "Downloads" section is now **Documents** (card grid with PDF previews from `static/home/documents/`).
- **Security:** chat limited to 40 messages/min per visitor, admin login to 8 tries / 10 min per IP, secure cookies, safe headers, debug mode OFF by default (set `FLASK_DEBUG=1` only on your own PC). **Set a long random `SECRET_KEY` and change `ADMIN_PASSWORD` in `.env` before going live.**
- **Extras:** `/healthz` (uptime check), `/manifest.webmanifest` (Add to Home screen), theme colour, screen-reader labels.

## Optional: WhatsApp Cloud API
Webhook `https://YOUR-DOMAIN/webhook` (verify token = `WA_VERIFY_TOKEN`); fill `WA_TOKEN`, `WA_PHONE_NUMBER_ID`. WhatsApp users are not asked for their number (it is known). To make the QR open WhatsApp instead, set `QR_URL=https://wa.me/91XXXXXXXXXX`.

## Files
app.py · bot.py · options.py · db.py (MongoDB) · pdfgen.py · whatsapp.py · static/logo.png · templates/ · uploads/

## Chat flow (follows the hand-drawn flowchart)
Start -> **Hi** (welcome + logo) -> **Home tab** (hero slider like ashokabuildcon.com) -> *Existing user?*
- **Existing user** -> Enquiry Form (Customer Details first if we do not know them yet)
- **New customer** -> About Us -> Products -> Resource -> Supply Chain -> Services -> Enquiry Form -> Contact Us
  (each page has a *Next* button; *All sections* in the menu opens any page directly)
- **Join our Team** (3rd option in the *Select user type* popup) -> Job Application form (the form is no longer in any other menu)

| Page | Sub options |
|---|---|
| Products | GI Pipe · MS Pipe (-> MS Black Pipe, Large Diameter Pipe) · Structural Hollow Sections · Seamless Pipe · GP Pipe |
| Resource | Product Catalogue · Certificates · Quality Assurance · Gallery · Documents |
| Supply Chain | Authorised Dealers & Distributors · Request For Quote · Vendor Registration · Clients |

Edit all texts / product tables in `options.py` (PRODUCT_INFO, ABOUT_TEXT, CLIENTS_TEXT ...). Home slider slides: `templates/home.html` (array `HS`), images in `static/home/`.
Job applications / vendor registrations are saved in MongoDB (`jobs`, `vendors`) and shown in Admin -> Jobs / Vendors.
Files for Catalogue / Certificates / Gallery / Documents: Admin -> Catalog files, or the `catalog/<catalogue|certificate|awards|datasheet|documents>/` folders.

## New: Hindi/English, Voice, WhatsApp confirmation, new Admin panel
- **Language switch (Hindi / English):** web chat → 🌐 button in the header. WhatsApp → customer types `hindi` / `english`. Choice is remembered per customer. All menus, buttons, forms, enquiry summary and confirmation switch language. Texts live in `i18n.py` (`EXACT`, `PHRASES`, `PATTERNS`) – anything not listed simply stays English. Hindi words (Devanagari) like `कीमत`, `संपर्क`, `उत्पाद` are understood (`INTENTS_HI` in `bot.py`).
- **Voice input:** web chat → 🎤 button next to Send (browser speech recognition, Chrome/Edge/Safari, needs https). WhatsApp voice notes → transcribed with OpenAI (`OPENAI_API_KEY`, see `voice.py`).
- **WhatsApp confirmation:** after every web enquiry the customer gets a WhatsApp message (`confirm.py`). Needs `WA_TOKEN`, `WA_PHONE_NUMBER_ID` and – for customers who never messaged you – an **approved template** (`WA_CONFIRM_TEMPLATE`). Admin → Enquiries shows Sent / Failed and a ↻ Send button.
- **Admin panel:** new sidebar layout, Dashboard (stats, 7-day chart, top products), colour status badges, mobile friendly.
