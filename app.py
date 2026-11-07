from urllib.parse import quote
import re
import os, io, csv, uuid, time, logging
from collections import defaultdict, deque
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
from bson import ObjectId
from flask import (Flask, request, session, redirect, url_for, render_template, flash,
                   send_from_directory, abort, Response, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
import db, bot, whatsapp, pdfgen, about_fetch, confirm, voice, vendor, mailer, job, sheet_quote, sales_quote
from db import database, norm, ser, fmt_phone

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024      # was 25 MB - several photos uploaded together need more room
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.getenv("PUBLIC_URL", "").lower().startswith("https"), PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30)
app.jinja_env.filters["fmt_phone"] = fmt_phone          # shows stored phone as "+91 9930988307" wherever used in templates
if app.secret_key == "dev-secret": logging.warning("SECRET_KEY is not set in .env - using an unsafe default. Set a long random SECRET_KEY before going live.")

# ---------- tiny in-memory rate limiter (per process) - stops spam / password guessing ----------
_HITS = defaultdict(deque)
def too_many(bucket, limit, seconds):
    now = time.time(); q = _HITS[bucket]
    while q and now - q[0] > seconds: q.popleft()
    if len(q) >= limit: return True
    q.append(now); return False
def client_ip(): return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "?")
UPLOADS = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS, exist_ok=True)
db.init(os.getenv("ADMIN_PHONE", "9930988307"), os.getenv("ADMIN_PASSWORD", "admin123"), os.getenv("ADMIN_NAME", "Admin"))

def site_url():
    return (os.getenv("PUBLIC_URL") or request.url_root).rstrip("/")

def qr_target():
    return os.getenv("QR_URL") or site_url() + "/"

# ---------- public: chatbot home (opened by QR scan) ----------
@app.after_request
def _no_cache(r):          # phones must always get the latest chat page / replies (no stale cached copy)
    if request.path in ("/", "/vendor-registration", "/chat/send", "/chat/lang", "/chat/reset", "/vendor/form", "/job/form"): r.headers["Cache-Control"] = "no-store, max-age=0"
    r.headers.setdefault("Permissions-Policy", "microphone=(self)")      # allow the chat page to use the microphone
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    r.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return r

@app.get("/manifest.webmanifest")
def manifest():            # lets phones "Add to Home screen" the chatbot like an app
    return jsonify(name="Shreeji SteelTubes Pvt. Ltd.", short_name="Shreeji", start_url="/", display="standalone",
                   background_color="#eef1f8", theme_color="#2E3F96",
                   icons=[{"src": "/static/logo.png", "sizes": "any", "type": "image/png"}])

@app.get("/healthz")
def healthz():             # for hosting uptime checks
    return jsonify(ok=True)

@app.route("/")
def home():
    return render_template("home.html", open_page="")

@app.route("/vendor-registration")
def vendor_registration_link():      # direct link (WhatsApp / QR / email): opens the site straight on the Vendor Registration page
    return render_template("home.html", open_page="vr")

@app.get("/products/data")
def products_data():       # product details for the Home page popup (same data the chat used to show)
    import options as OPT
    out = {k: {"label": v[0], "img": OPT.H + v[1], "title": v[2], "rows": [list(r) for r in v[3]], "desc": v[4]}
           for k, v in OPT.PRODUCT_INFO.items()}
    return jsonify(out)

@app.get("/about/data")
def about_data():          # About Us details read live from https://www.shreejisteeltubes.com/about-us/ (cached, falls back to built-in copy)
    r = jsonify(about_fetch.get_about(force=request.args.get("refresh") == "1"))
    r.headers["Cache-Control"] = "no-store, max-age=0"; return r

@app.get("/contacts/data")
def contacts_data():       # department-wise contacts (Admin -> Contacts) for the 'doubt? contact us' popup before the enquiry form
    r = jsonify(bot.contact_rows()); r.headers["Cache-Control"] = "no-store, max-age=0"; return r

@app.get("/resources/data")
def resources_data():      # everything under 'Resources' (catalogue / certificates / QA / gallery / documents) for the web-chat popup
    import options as OPT
    def L(cat):
        rows = []
        for u, fn, t in bot.catalog_docs(cat):
            x = {"title": t, "name": fn, "url": u}
            stem = os.path.splitext(fn)[0]         
            tdir = {"certificate": "cert", "catalogue": "catalogue", "datasheet": "documents", "documents": "documents"}.get(cat)      # card picture: static/home/<cert|catalogue|documents>/<same file name>.jpg
            if tdir and os.path.isfile(os.path.join(os.path.dirname(__file__), "static", "home", tdir, stem + ".jpg")):
                x["thumb"] = "/static/home/" + tdir + "/" + quote(stem) + ".jpg"
            rows.append(x)
        return rows
    r = jsonify(catalogue=L("catalogue"), certificate=L("certificate"), awards=L("awards"), downloads=L("datasheet") + L("documents"), godown=L("godown"), office=L("office"),
                qa=OPT.QA_TEXT, qa_img=OPT.H + "awards.jpg", gallery=[{"img": u, "cap": c} for u, c in OPT.GALLERY_IMAGES])
    r.headers["Cache-Control"] = "no-store, max-age=0"; return r

_LV = {"t": 0.0, "v": ""}
def _live_sig():
    """Fingerprint of everything Admin can change on the public site (documents, photos, catalog folders, contacts). Cached 2 s."""
    import hashlib
    now = time.time()
    if now - _LV["t"] < 2 and _LV["v"]: return _LV["v"]
    parts = []
    for d in database().documents.find():
        fn = d.get("filename", "")
        parts.append(f"D|{d.get('_id')}|{d.get('category')}|{fn}|{d.get('title')}|{int(os.path.isfile(os.path.join(UPLOADS, secure_filename(fn))))}")
    for r in database().contacts.find():
        parts.append("C|" + str(r.get("_id")) + "|" + "|".join(str(r.get(k, "")) for k in ("department", "name", "designation", "phone", "email", "direct_line")))
    for cat, _ in DOC_CATS:                       # files dropped straight into catalog/<category>/ folders
        folder = os.path.join(bot.CATALOG_DIR, cat); hid = bot.hidden_folder_files(cat)
        if os.path.isdir(folder):
            for fn in os.listdir(folder):
                fp = os.path.join(folder, fn)
                if os.path.isfile(fp) and fn not in hid: parts.append(f"F|{cat}|{fn}|{int(os.path.getmtime(fp))}|{os.path.getsize(fp)}")
    _LV["v"] = hashlib.md5("\n".join(sorted(parts)).encode()).hexdigest()[:12]; _LV["t"] = now
    return _LV["v"]

@app.get("/live/version")
def live_version():        # open screens poll this; when the value changes they reload catalogue / certificates / photos / contacts by themselves
    r = jsonify(v=_live_sig()); r.headers["Cache-Control"] = "no-store, max-age=0"; return r

@app.post("/chat/send")
def chat_send():
    sid = session.setdefault("sid", uuid.uuid4().hex)
    if too_many("chat:" + sid, 40, 60) or too_many("chatip:" + client_ip(), 120, 60):      # 40 msgs / minute per visitor
        return jsonify(replies=[{"type": "text", "text": "\u23F3 You are sending messages too fast. Please wait a few seconds and try again."}]), 429
    box = []; tok = whatsapp.collector.set(box)
    try: bot.handle("web:" + sid, (request.get_json(silent=True) or {}).get("text", "hi"))
    finally: whatsapp.collector.reset(tok)
    return jsonify(replies=box, lang=db.get_lang("web:" + sid))

# ---------- Request For Quote page (Supply Chain > Request For Quote): saved as a normal enquiry -> admin panel / PDF / CSV ----------
@app.post("/rfq/submit")
def rfq_submit():
    import re
    sid = session.setdefault("sid", uuid.uuid4().hex)
    if too_many("rfq:" + sid, 5, 600) or too_many("rfqip:" + client_ip(), 20, 600):
        return jsonify(ok=False, errors={"_": "Too many requests. Please wait a few minutes and try again."}), 429
    d = request.get_json(silent=True) or {}
    g = lambda k, n: str(d.get(k) or "").strip()[:n]
    firm, gst, contact, email, desc = g("firm", 120), g("gst", 20).upper().replace(" ", ""), g("contact", 40), g("email", 120), g("desc", 1500)
    errs = {}
    if len(firm) < 2: errs["firm"] = "Please enter the name of your firm"
    if gst and not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gst): errs["gst"] = "Enter a valid 15-character GST number (or leave blank)"
    if len(re.sub(r"\D", "", contact)) < 10: errs["contact"] = "Enter a valid contact number (10 digits)"
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", email): errs["email"] = "Enter a valid email address"
    if len(desc) < 3: errs["desc"] = "Please describe your requirement"
    if errs: return jsonify(ok=False, errors=errs), 400
    no = db.next_no()
    doc = {"no": no, "source": "rfq-page", "status": "New", "created": db.now_ist(), "name": firm, "phone": contact, "customer_location": "-", "location": "-",
           "company": firm, "gst": gst or "-", "uc_code": "-", "portal_access": "-", "reps": "-", "email": email, "product": "Request For Quote",
           "size": "-", "thickness": "-", "length": "-", "qty": "-", "grade": "-", "standard": "-", "brand": "-", "delivery_date": "-",
           "remarks": desc + "\nEmail: " + email, "lang": "en"}
    database().enquiries.insert_one(doc)
    n = os.getenv("NOTIFY_NUMBER")
    if n:
        try: whatsapp.send_text(n, f"New Request For Quote #{no}: {firm} {contact} {email} - {desc[:200]}")
        except Exception: logging.exception("RFQ notify failed")
    return jsonify(ok=True, no=no)

# ---------- Contact page (Send a Message form -> saved as a normal enquiry) ----------
@app.post("/contact/submit")
def contact_submit():
    import re
    sid = session.setdefault("sid", uuid.uuid4().hex)
    if too_many("ct:" + sid, 5, 600) or too_many("ctip:" + client_ip(), 20, 600):
        return jsonify(ok=False, errors={"_": "Too many requests. Please wait a few minutes and try again."}), 429
    d = request.get_json(silent=True) or {}
    g = lambda k, n: str(d.get(k) or "").strip()[:n]
    fn, ln, email, phone, comp, subj, msg = g("fn", 60), g("ln", 60), g("email", 120), g("phone", 40), g("company", 120), g("subject", 150), g("message", 1500)
    errs = {}
    if len(fn) < 2: errs["fn"] = "Please enter your first name"
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", email): errs["email"] = "Enter a valid email address"
    if len(re.sub(r"\D", "", phone)) < 10: errs["phone"] = "Enter a valid phone number (10 digits)"
    if len(msg) < 3: errs["message"] = "Please write your message"
    if errs: return jsonify(ok=False, errors=errs), 400
    no = db.next_no(); name = (fn + " " + ln).strip()
    doc = {"no": no, "source": "contact-page", "status": "New", "created": db.now_ist(), "name": name, "phone": phone, "customer_location": "-", "location": "-",
           "company": comp or "-", "gst": "-", "uc_code": "-", "portal_access": "-", "reps": "-", "email": email, "product": "Contact Message",
           "size": "-", "thickness": "-", "length": "-", "qty": "-", "grade": "-", "standard": "-", "brand": "-", "delivery_date": "-",
           "remarks": (("Subject: " + subj + "\n") if subj else "") + msg + "\nEmail: " + email, "lang": "en"}
    database().enquiries.insert_one(doc)
    n = os.getenv("NOTIFY_NUMBER")
    if n:
        try: whatsapp.send_text(n, f"New Contact Message #{no}: {name} {phone} {email} - {msg[:200]}")
        except Exception: logging.exception("Contact notify failed")
    return jsonify(ok=True, no=no)

# ---------- Vendor Registration page (Supply Chain > Vendor Registration): full form like the paper 'Vendor Registration Form' ----------
@app.get("/vendor/form")
def vendor_form_data():
    return jsonify(ok=True, form=vendor.form(), date=db.now_ist().strftime("%d-%m-%Y"))

# ---------- Job Application page: form like the enquiry form + resume (PDF) upload ----------
@app.get("/job/form")
def job_form_data():
    return jsonify(ok=True, form=job.form())

@app.post("/job/submit")
def job_submit():
    sid = session.setdefault("sid", uuid.uuid4().hex)
    if too_many("job:" + sid, 5, 600) or too_many("jobip:" + client_ip(), 20, 600):
        return jsonify(ok=False, errors={"_": "Too many requests. Please wait a few minutes and try again."}), 429
    v, errs = job.clean(request.form)
    got, ferrs = job.read_resume(request.files); errs.update(ferrs)
    if errs: return jsonify(ok=False, errors=errs), 400
    ors = [{"phone": v["phone"]}]                                   # one application per applicant: same mobile or same email = already applied
    if v.get("email"): ors.append({"email": {"$regex": "^" + re.escape(v["email"]) + "$", "$options": "i"}})
    if database().jobs.find_one({"$or": ors}):
        return jsonify(ok=False, errors={"_": "You have already submitted an application with this email / mobile number. Our HR team will contact you if your profile matches."}), 409
    no = db.next_no("job")
    doc = dict(v); doc.update(no=no, source="web", status="New", created=db.now_ist(), resume=job.save_resume(no, got))
    database().jobs.insert_one(doc)
    try: mailer.start_job(doc)                  # email applicant details + resume (PDF) to the admin(s), in a background thread
    except Exception: logging.exception("Job mail failed")
    n = os.getenv("NOTIFY_NUMBER")
    if n:
        try: whatsapp.send_text(n, f"New job application #{no}: {v['name']} ({v['position']}), {v['phone']} - resume preview/download is on the admin page")
        except Exception: logging.exception("Job notify failed")
    return jsonify(ok=True, no=no)

@app.errorhandler(413)
def too_big(e):
    if request.path == "/job/submit":
        return jsonify(ok=False, errors={"_": "The file is too large. Please keep your resume under 3 MB."}), 413
    if request.path == "/vendor/submit":
        return jsonify(ok=False, errors={"_": "The files are too large. Please keep each document under 3 MB."}), 413
    return "File too large", 413

@app.post("/vendor/submit")
def vendor_submit():
    import secrets
    sid = session.setdefault("sid", uuid.uuid4().hex)
    if too_many("vnd:" + sid, 5, 600) or too_many("vndip:" + client_ip(), 20, 600):
        return jsonify(ok=False, errors={"_": "Too many requests. Please wait a few minutes and try again."}), 429
    v, errs = vendor.clean(request.form)
    got, ferrs = vendor.read_files(request.files); errs.update(ferrs)
    V = database().vendors
    if not errs.get("pan") and v["pan"]:                                   # one registration per PAN / GST
        d = V.find_one({"pan": v["pan"]})
        if d: errs["pan"] = f"A registration with this PAN already exists (No. {d['no']}). Please contact our team to update your details."
    if not errs.get("gst") and v["gst"]:
        d = V.find_one({"gst": v["gst"]})
        if d: errs["gst"] = f"A registration with this GST number already exists (No. {d['no']}). Please contact our team to update your details."
    if errs: return jsonify(ok=False, errors=errs), 400
    no = db.next_no("vendor")
    doc = dict(v); doc.pop("agree", None)
    doc.update(no=no, source="web", status="New", created=db.now_ist(), agree=True, files=vendor.save_files(no, got),
               dl_token=secrets.token_urlsafe(16), vendor_code="", verified_by="", approved_by="", office_date="",
               company=v["firm"], name=v["contact"], phone=v["mobile"], supplies=v["products"], years="")    # + the short names the older admin pages use
    V.insert_one(doc)
    n = os.getenv("NOTIFY_NUMBER")
    if n:
        try: whatsapp.send_text(n, f"New vendor registration #{no}: {v['firm']} ({v['vtype'] or 'vendor'}), {v['contact']} {v['mobile']} - {v['products'][:150]}")
        except Exception: logging.exception("Vendor notify failed")
    return jsonify(ok=True, no=no, ref=vendor.ref(doc), t=doc["dl_token"])

@app.get("/vendor/<int:no>/pdf")
def vendor_pdf_public(no):       # the vendor's own copy of the filled form (private key in the link, like the enquiry receipt)
    import hmac
    if too_many("vpdfip:" + client_ip(), 30, 600): abort(429)
    v = database().vendors.find_one({"no": no})
    tok = request.args.get("t", "")
    if not v or not v.get("dl_token") or not hmac.compare_digest(str(v["dl_token"]), tok): abort(404)
    r = Response(pdfgen.vendor(v), mimetype="application/pdf", headers={"Content-Disposition": f"attachment; filename=Vendor_Registration_{no}.pdf"})
    r.headers["Cache-Control"] = "no-store"; return r

# ---------- customer: official PDF of the submitted enquiry (opened by the 'OK' button of the Thank-you popup) ----------
@app.get("/enquiry/<int:no>/pdf")
def customer_enquiry_pdf(no):
    import hmac
    if too_many("pdfip:" + client_ip(), 30, 600): abort(429)
    e = database().enquiries.find_one({"no": no})
    tok = request.args.get("t", "")
    if not e or not e.get("dl_token") or not hmac.compare_digest(str(e["dl_token"]), tok): abort(404)     # wrong / missing key -> same 404 as a missing enquiry
    r = Response(pdfgen.single(e), mimetype="application/pdf",
                 headers={"Content-Disposition": f"attachment; filename=Shreeji_Enquiry_{no}.pdf"})
    r.headers["Cache-Control"] = "no-store"; return r

GST_USED_MSG = "This GST number is already registered with us. A GST number can be used by a New Customer only once - please choose Existing Customer and use your UC code."

# ---------- GST check while the customer types: existing -> UC code from DB, new -> verified on GST portal + UC code generated ----------
@app.get("/gst/lookup")
def gst_lookup():
    import gstverify
    sid = session.setdefault("sid", uuid.uuid4().hex)
    if too_many("gst:" + sid, 15, 600) or too_many("gstip:" + client_ip(), 60, 600):
        return jsonify(ok=False, error="Too many checks. Please wait a few minutes and try again."), 429
    g = gstverify.clean(request.args.get("gst"))
    if len(g) != 15: return jsonify(ok=False, error="GST number must be 15 characters."), 400
    r = gstverify.resolve(g)
    out = jsonify(ok=r["ok"], error=r.get("error", ""), uc_code=r.get("uc_code", ""), name=r.get("name", ""),
                  legal=r.get("legal", ""), trade=r.get("trade", ""),
                  existing=r.get("existing", False), status=r.get("status", ""),
                  registered=bool(r["ok"] and gstverify.is_customer(g)))      # True -> a New User cannot register this GST again
    out.headers["Cache-Control"] = "no-store"; return out, (200 if r["ok"] or not r.get("temp") else 503)

# ---------- Existing customer: UC code -> details saved when the customer first registered as a new user ----------
@app.get("/uc/lookup")
def uc_lookup():
    import gstverify
    sid = session.setdefault("sid", uuid.uuid4().hex)
    if too_many("uc:" + sid, 12, 600) or too_many("ucip:" + client_ip(), 40, 600):     # UC codes are sequential -> stop guessing / scraping
        return jsonify(ok=False, error="Too many attempts. Please wait a few minutes and try again."), 429
    if request.args.get("gst"):          # existing customer who does not remember the UC code -> GST number (no portal call, no new UC code)
        rec = gstverify.find_by_gst(request.args.get("gst"))
        miss = "This GST number is not registered with us. Please check it, or register as a new customer."
    else:
        rec = gstverify.find_by_uc(request.args.get("uc"))
        miss = "UC code not found. Please check the code and try again."
    if not rec:
        out = jsonify(ok=False, error=miss); out.headers["Cache-Control"] = "no-store"; return out, 404
    # the real mobile / email never leave the server: the page shows them masked, the submit step re-reads them from the database
    out = jsonify(ok=True, uc_code=rec["uc_code"], name=rec["name"], company=rec["company"], gst=rec["gst"],
                  mobile=gstverify.mask_mobile(rec["mobile"]), email=gstverify.mask_email(rec["email"]))
    out.headers["Cache-Control"] = "no-store"; return out

# ---------- Enquiry Form PAGE for existing customers (Contact-page style): form schema + submit ----------
@app.get("/enquiry/form")
def enquiry_form_data():
    sid = session.setdefault("sid", uuid.uuid4().hex); key = "web:" + sid
    cust = database().customers.find_one({"_id": key})
    _, data = db.get_state(key)
    if request.args.get("mode") in ("exist", "new"): db.set_utype(key, request.args["mode"])      # 'Already our customer?' / 'New customer?' switch on the page
    mode = db.get_utype(key)
    form = bot.enquiry_form((data or {}).get("vals") or {})
    if not cust:      # new device / browser: the same page, with a "Your Details" block on top (no separate chat form needed)
        form["sections"].insert(0, {"title": "Your Details", "fields": bot.page_customer_fields(mode)})
    r = jsonify(ok=True, form=form, need_cust=not cust, mode=mode,
                cust={k: (cust or {}).get(k, "") for k in ("name", "company", "phone", "gst", "uc_code")})
    r.headers["Cache-Control"] = "no-store, max-age=0"; return r

@app.post("/enquiry/submit")
def enquiry_submit():
    sid = session.setdefault("sid", uuid.uuid4().hex); key = "web:" + sid
    if too_many("enq:" + sid, 10, 600) or too_many("enqip:" + client_ip(), 40, 600):
        return jsonify(ok=False, errors={"_": "Too many requests. Please wait a few minutes and try again."}), 429
    body = request.get_json(silent=True) or {}
    vals, items = body.get("values"), body.get("items") or []
    if not isinstance(vals, dict): return jsonify(ok=False, errors={"_": "Invalid form data."}), 400
    if not isinstance(items, list) or len(items) > bot.MAX_ITEMS - 1 or any(not isinstance(i, dict) for i in items):
        return jsonify(ok=False, errors={"_": "Invalid form data."}), 400
    vals = {str(k): v for k, v in vals.items()}
    items = [{str(k): v for k, v in i.items()} for i in items]       # extra products of the same enquiry ("+ Add another product")
    cust = database().customers.find_one({"_id": key})
    box = []; tok = whatsapp.collector.set(box); bot.KEY.set(key); whatsapp.LANG.set(db.get_lang(key))
    try:
        if not cust:      # first enquiry from this device: validate "Your Details" + the enquiry together, then save the customer
            exist = db.get_utype(key) == "exist"
            if exist:      # Existing Customer: UC code -> saved details from the database (what the browser sent for name / company is ignored)
                import gstverify
                ident = gstverify.clean_uc(vals.get("c_uc"))          # ONE box: a UC code ... or the GST number when the code is not remembered
                if not ident: return jsonify(ok=False, errors={"c_uc": "Please enter your UC code or GST number."}), 400
                if gstverify.GST_RE.match(ident):
                    rec = gstverify.find_by_gst(ident)
                    if not rec: return jsonify(ok=False, errors={"c_uc": "This GST number is not registered with us. Please check it, or register as a new customer."}), 400
                else:
                    rec = gstverify.find_by_uc(ident)
                    if not rec: return jsonify(ok=False, errors={"c_uc": "UC code not found. Please check the code and try again."}), 400
                if not rec.get("uc_code") or not gstverify.GST_RE.match(gstverify.clean(rec.get("gst"))):     # Existing Customer: submit only when BOTH the UC code and the GST number exist
                    return jsonify(ok=False, errors={"c_uc": "Both UC code and GST number are required, but one of them is missing for this customer. Please contact us."}), 400
                vals = {**vals, "c_uc": rec["uc_code"], "c_gst": rec["gst"], "c_company": rec["company"],
                        "c_name": rec["name"] or vals.get("c_name", ""), "c_mobile": rec["mobile"] or vals.get("c_mobile", ""),
                        "c_email": rec["email"] or vals.get("c_email", "")}
            else:          # New User: the UC code is generated from the verified GST - a typed value is never trusted
                import gstverify
                if gstverify.is_customer(vals.get("c_gst")):       # one GST number = one New User registration; after that only 'Existing Customer'
                    return jsonify(ok=False, errors={"c_gst": GST_USED_MSG}), 400
                vals = {**vals, "c_uc": ""}
            _, cerrs = bot.validate_customer(bot.page_customer_vals(vals), None)
            _, eerrs = bot.validate_enquiry(vals)
            errs = {**bot.page_customer_errs(cerrs), **(eerrs or {})}
            if exist and "c_gst" in errs: errs["c_uc"] = errs.pop("c_gst")       # Existing Customer has ONE box (UC code / GST) - show a GST problem under it
            _, ierrs = bot.validate_items(items)
            if ierrs: errs["_items"] = ierrs
            if errs: return jsonify(ok=False, errors=errs), 400
            errs = bot.submit(key, key, None, "customer", bot.page_customer_vals(vals), None)
            if errs: return jsonify(ok=False, errors=bot.page_customer_errs(errs)), 400
            if exist: database().customers.update_one({"_id": key}, {"$set": {"via_exist": True}})      # a copy made by an Existing Customer - only the New User record keeps the UC code usable
            cust = database().customers.find_one({"_id": key})
            box.clear()
        errs = bot.submit(key, key, None, "enquiry", vals, cust, items)
    finally: whatsapp.collector.reset(tok)
    if errs: return jsonify(ok=False, errors=errs), 400
    th = [m for m in box if m.get("thanks")]          # chat bubble with the Thank-you popup data + 'Download Enquiry PDF' button
    return jsonify(ok=True, replies=th, thanks=(th[0]["thanks"] if th else None))

@app.post("/chat/reset")
def chat_reset():          # page refreshed -> the visitor starts a fresh conversation (language choice is kept)
    sid = session.setdefault("sid", uuid.uuid4().hex)
    database().chat_state.update_one({"_id": "web:" + sid}, {"$set": {"state": "MENU", "data": {}}, "$unset": {"utype": ""}}, upsert=True)
    return jsonify(ok=True)

@app.get("/chat/lang")
def chat_lang():           # the chat page asks which language this visitor chose (header button + microphone use it)
    sid = session.setdefault("sid", uuid.uuid4().hex)
    return jsonify(lang=db.get_lang("web:" + sid))

@app.route("/qr.png")
def qr_png():
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    q.add_data(qr_target()); q.make(fit=True)
    buf = io.BytesIO(); q.make_image(fill_color="#2E3F96", back_color="white").save(buf, "PNG")
    return Response(buf.getvalue(), mimetype="image/png")

@app.route("/catalog-files/<cat>/<path:name>")   # public: files kept in the project's catalog/<category>/ folders
def catalog_files(cat, name):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "catalog", secure_filename(cat)), name,
                               as_attachment=bool(request.args.get("dl")))

@app.route("/files/<path:name>")   # public: chat / WhatsApp download catalog files from here
def files(name): return send_from_directory(UPLOADS, name, as_attachment=bool(request.args.get("dl")))

# ---------- WhatsApp webhook (optional) ----------
@app.get("/webhook")
def verify():
    if request.args.get("hub.verify_token") == os.getenv("WA_VERIFY_TOKEN"):
        return request.args.get("hub.challenge", ""), 200
    return "forbidden", 403

@app.post("/webhook")
def incoming():
    try:
        for e in (request.get_json(silent=True) or {}).get("entry", []):
            for ch in e.get("changes", []):
                for m in ch["value"].get("messages", []):
                    phone = norm(m["from"])
                    if m["type"] == "audio":            # voice note -> text -> same bot logic (needs OPENAI_API_KEY, see voice.py)
                        bot.handle_voice("wa:" + phone, voice.transcribe_whatsapp_audio(m["audio"]["id"]), phone)
                        continue
                    text = m.get("text", {}).get("body", "") if m["type"] == "text" else "menu"
                    bot.handle("wa:" + phone, text, phone=phone)
    except Exception as ex:
        print("webhook error:", ex)
    return "ok", 200

# ---------- admin auth ----------
def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if "admin_id" not in session: return redirect(url_for("admin_login"))
        try:
            me = database().admins.find_one({"_id": ObjectId(session["admin_id"])}, {"active": 1, "name": 1})
        except Exception:
            me = None
        if not me or not me.get("active", True):          # deleted or disabled while logged in -> sign out immediately
            session.pop("admin_id", None); session.pop("admin_name", None)
            flash("Your admin account is no longer active. Please contact another admin.")
            return redirect(url_for("admin_login"))
        session["admin_name"] = me["name"]
        return f(*a, **k)
    return w

def find_admin_by_login(ident):
    """Login with either the admin's username (case-insensitive) or the 10-digit mobile number."""
    ident = (ident or "").strip()
    if not ident: return None
    A = database().admins
    a = A.find_one({"username": ident.lower()})
    if not a:
        digits = "".join(ch for ch in ident if ch.isdigit())
        if len(digits) >= 10: a = A.find_one({"phone": norm(digits[-10:] if len(digits) > 10 else digits)})
    return a

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if too_many("login:" + client_ip(), 8, 600):          # 8 tries / 10 minutes per IP
            flash("Too many attempts. Please wait 10 minutes and try again."); return render_template("login.html"), 429
        ident = (request.form.get("login") or request.form.get("phone") or "").strip()
        a = find_admin_by_login(ident)
        if a and a.get("active", True) and check_password_hash(a["password_hash"], request.form.get("password", "")):
            session.update(admin_id=str(a["_id"]), admin_name=a["name"])
            try:                                               # keep the readable (encrypted) copy in step with the real password
                pw = request.form.get("password", "")
                if _dec_pw(a.get("password_enc")) != pw:
                    database().admins.update_one({"_id": a["_id"]}, {"$set": {"password_enc": _enc_pw(pw)}})
            except Exception as ex: print("password_enc save failed:", ex)
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username / mobile number or password")
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None); session.pop("admin_name", None); return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def admin_index(): return redirect(url_for("admin_dashboard"))

# ---------- admin: dashboard (numbers at a glance) ----------
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    from datetime import timedelta
    D = database(); today = db.now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    enq = D.enquiries
    days = []                                          # last 7 days, oldest first (for the bar chart)
    for i in range(6, -1, -1):
        d0 = today - timedelta(days=i)
        days.append({"label": d0.strftime("%a"), "date": d0.strftime("%d %b"),
                     "n": enq.count_documents({"created": {"$gte": d0, "$lt": d0 + timedelta(days=1)}})})
    top = {}
    for e in enq.find({}, {"product": 1}):
        top[e.get("product") or "-"] = top.get(e.get("product") or "-", 0) + 1
    stats = dict(total=enq.count_documents({}), today=enq.count_documents({"created": {"$gte": today}}),
                 new=enq.count_documents({"status": "New"}), quoted=enq.count_documents({"status": "Quoted"}),
                 closed=enq.count_documents({"status": "Closed"}), customers=D.customers.count_documents({}),
                 jobs=D.jobs.count_documents({}), vendors=D.vendors.count_documents({}),
                 hindi=enq.count_documents({"lang": "hi"}), wa_sent=enq.count_documents({"wa_confirm": "sent"}),
                 wa_failed=enq.count_documents({"wa_confirm": "failed"}))
    return render_template("admin_dashboard.html", s=stats, days=days, peak=max([d["n"] for d in days] + [1]),
                           top=sorted(top.items(), key=lambda x: -x[1])[:6],
                           recent=list(enq.find().sort("no", -1).limit(8)),
                           wa_on=confirm.enabled(), voice_on=voice.enabled())

# ---------- admin: enquiries (view, PDF, CSV) ----------
ENQ_PER_PAGE = 50          # enquiries shown on one admin page

def enquiry_filter(src=None):
    src = request.args if src is None else src          # src = request.form for the bulk-delete
    f = {}
    st, s = src.get("status", ""), src.get("q", "").strip()
    if st: f["status"] = st
    if s:
        import re; rx = {"$regex": re.escape(s), "$options": "i"}
        f["$or"] = [{k: rx} for k in ("name", "phone", "company", "gst", "product", "size")]
    return f

def find_enquiries():       # used by CSV / PDF export: ALL matching enquiries, oldest first (same order as the screen)
    return list(database().enquiries.find(enquiry_filter()).sort("no", 1))

@app.route("/admin/enquiries")
@admin_required
def admin_enquiries():
    E = database().enquiries
    counts = {"all": E.count_documents({}), **{st: E.count_documents({"status": st}) for st in ("New", "Quoted", "Closed")}}
    f = enquiry_filter()
    total = E.count_documents(f)
    pages = max(1, -(-total // ENQ_PER_PAGE))                    # ceil
    try: page = int(request.args.get("page", ""))
    except ValueError: page = pages                              # no page given -> open the LAST page (newest enquiries)
    page = min(max(page, 1), pages)
    # oldest first: new enquiries are added at the BOTTOM; 50 per page, only this page is read from MongoDB
    rows = list(E.find(f).sort("no", 1).skip((page - 1) * ENQ_PER_PAGE).limit(ENQ_PER_PAGE))
    return render_template("admin_enquiries.html", enq=rows, counts=counts,
                           status=request.args.get("status", ""), q=request.args.get("q", ""),
                           page=page, pages=pages, total=total, per=ENQ_PER_PAGE,
                           first_no=(page - 1) * ENQ_PER_PAGE + 1 if total else 0,
                           last_no=(page - 1) * ENQ_PER_PAGE + len(rows))

@app.post("/admin/enquiries/<int:no>/status")
@admin_required
def set_status(no):
    database().enquiries.update_one({"no": no}, {"$set": {"status": request.form["status"]}})
    return redirect(request.referrer or url_for("admin_enquiries"))

@app.post("/admin/enquiries/<int:no>/resend-wa")
@admin_required
def resend_wa(no):         # send the WhatsApp confirmation again (e.g. after the template was approved)
    e = database().enquiries.find_one({"no": no}) or abort(404)
    ok, err = confirm.send(e)
    database().enquiries.update_one({"no": no}, {"$set": {"wa_confirm": "sent" if ok else "failed", "wa_confirm_note": err[:400], "wa_confirm_at": db.now_ist()}})
    flash(f"WhatsApp confirmation for enquiry #{no}: " + ("sent ✅" if ok else "failed ❌ – " + err))
    return redirect(request.referrer or url_for("admin_enquiries"))

@app.post("/admin/enquiries/<int:no>/resend-mail")
@admin_required
def resend_mail(no):       # email the enquiry PDF to the admins again (e.g. after an admin's email was added/fixed)
    e = database().enquiries.find_one({"no": no}) or abort(404)
    ok, note = mailer.send(e)
    database().enquiries.update_one({"no": no}, {"$set": {"admin_mail": "sent" if ok else "failed", "admin_mail_note": note[:400], "admin_mail_at": db.now_ist()}})
    flash(f"Enquiry PDF mail for #{no}: " + ("sent ✅" if ok else "failed ❌ – " + note))
    return redirect(request.referrer or url_for("admin_enquiries"))

@app.post("/admin/enquiries/<int:no>/resend-sheet-quote")
@admin_required
def resend_sheet_quote(no):   # email the customer the Google Sheet price/stock again (e.g. after fixing the sheet / product match)
    e = database().enquiries.find_one({"no": no}) or abort(404)
    matches = sheet_quote.find_matches(e.get("product"), e.get("size"), e.get("thickness"))
    ok, note = sheet_quote.send(e, matches)
    st = "sent" if ok else "failed"
    note = (note + (" (0 rows matched in sheet)" if not matches else f" ({len(matches)} row(s) matched)")) if ok else note
    database().enquiries.update_one({"no": no}, {"$set": {"sheet_quote": st, "sheet_quote_note": note[:400], "sheet_quote_at": db.now_ist()}})
    flash(f"Price/stock mail for #{no}: " + ("sent ✅ " + note if ok else "failed ❌ – " + note))
    return redirect(request.referrer or url_for("admin_enquiries"))

# ---------- SALES person: write the price -> customer gets it by mail at once (link comes in the sales person's mail; token = HMAC, no login) ----------
@app.route("/quote/<int:no>/<token>", methods=["GET", "POST"])
def sales_quote_page(no, token):
    if not sales_quote.token_ok(no, token): abort(404)
    e = database().enquiries.find_one({"no": no}) or abort(404)
    msg = err = ""
    if request.method == "POST":
        if too_many("sq:" + client_ip(), 30, 600): return "Too many requests. Please wait a few minutes.", 429
        text = (request.form.get("price") or "").strip()
        if not text: err = "Please write the price first."
        elif len(text) > 4000: err = "Message is too long (max 4000 characters)."
        else:
            ok, note = sales_quote.deliver(no, text, "link", reply_to=(sales_quote.sales_emails() or [None])[0])
            if ok: msg = "✅ Price sent to the customer (" + note + ")."
            else: err = "❌ Could not send: " + note
            e = database().enquiries.find_one({"no": no})
    r = Response(render_template("sales_quote.html", e=e, checks=sales_quote.check_all(e), msg=msg, err=err, rowtext=sales_quote._row_text,
                                 label=sales_quote.LABEL, items=sales_quote.items_of(e), draft=request.form.get("price", "") if err else ""))
    r.headers["Cache-Control"] = "no-store"; r.headers["X-Robots-Tag"] = "noindex, nofollow"; return r

@app.post("/admin/enquiries/<int:no>/resend-sales-mail")
@admin_required
def resend_sales_mail(no):       # mail the availability + "write price" link to the sales person again
    e = database().enquiries.find_one({"no": no}) or abort(404)
    ok, note = sales_quote.send_to_sales(e)
    database().enquiries.update_one({"no": no}, {"$set": {"sq_sales_mail": "sent" if ok else "failed", "sq_sales_note": note[:400], "sq_sales_at": db.now_ist()}})
    flash(f"Sales mail for #{no}: " + ("sent ✅ " + note if ok else "failed ❌ – " + note))
    return redirect(request.referrer or url_for("admin_enquiries"))

# ---------- admin: Settings page (sales price mail: on/off, website address, reply-by-mail / IMAP) - saved in MongoDB, overrides .env ----------
sales_quote.DECRYPT = lambda t: _dec_pw(t) or ""
@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    S = database().settings
    cur = S.find_one({"_id": "sales"}) or {}
    if request.method == "POST":
        f = request.form; errs = []
        url = f.get("PUBLIC_URL", "").strip().rstrip("/")
        if url and not re.fullmatch(r"https?://[^\s/]+(/[^\s]*)?", url): errs.append("Website address must start with http:// or https://")
        extra = [x.strip() for x in f.get("SALES_MAIL", "").split(",") if x.strip()]
        if any(not _EMAIL_RE.fullmatch(x) for x in extra): errs.append("Extra sales email is not valid")
        port = f.get("IMAP_PORT", "").strip() or "993"
        secs = f.get("SALES_POLL_SECONDS", "").strip() or "30"
        if not (port.isdigit() and secs.isdigit() and int(secs) >= 10): errs.append("IMAP port must be a number and check-interval at least 10 seconds")
        if errs:
            for x in errs: flash(x)
        else:
            d = {"SALES_QUOTE": "1" if f.get("SALES_QUOTE") else "0", "PUBLIC_URL": url, "SALES_MAIL": ", ".join(extra),
                 "SALES_IMAP_POLL": "1" if f.get("SALES_IMAP_POLL") else "0", "IMAP_HOST": f.get("IMAP_HOST", "").strip(),
                 "IMAP_PORT": port, "IMAP_USER": f.get("IMAP_USER", "").strip(), "SALES_POLL_SECONDS": secs}
            if f.get("IMAP_PASS", "").strip(): d["IMAP_PASS"] = _enc_pw(f["IMAP_PASS"].strip())      # blank = keep the saved one
            if f.get("clear_pass"): d["IMAP_PASS"] = ""
            S.update_one({"_id": "sales"}, {"$set": d}, upsert=True)
            sales_quote.refresh_cfg(); flash("Settings saved ✅ (applies immediately, no restart needed)")
            return redirect(url_for("admin_settings"))
    g = lambda k, dflt="": cur.get(k) if cur.get(k) not in (None,) else (os.getenv(k, dflt) if k != "IMAP_PASS" else "")
    v = {k: g(k, d) for k, d in (("SALES_QUOTE", "1"), ("PUBLIC_URL", ""), ("SALES_MAIL", ""), ("SALES_IMAP_POLL", "0"),
                                  ("IMAP_HOST", ""), ("IMAP_PORT", "993"), ("IMAP_USER", ""), ("SALES_POLL_SECONDS", "30"))}
    sales = [a for a in database().admins.find({"active": True, "sales_notify": True})]
    return render_template("admin_settings.html", v=v, has_pass=bool(cur.get("IMAP_PASS")), smtp_ok=sales_quote.smtp_ready(),
                           smtp_user=os.getenv("SMTP_USER", ""), sales=sales, req_host=request.url_root.rstrip("/"))

@app.post("/admin/enquiries/<int:no>/delete")
@admin_required
def delete_enquiry(no):
    database().enquiries.delete_one({"no": no}); db.sync_enquiry_counter(); return redirect(url_for("admin_enquiries"))

@app.post("/admin/enquiries/bulk-delete")
@admin_required
def bulk_delete_enquiries():       # delete the ticked enquiries, or ALL enquiries matching the current tab/search ("Select all N")
    E = database().enquiries
    if request.form.get("all") == "1":
        n = E.delete_many(enquiry_filter(request.form)).deleted_count
    else:
        nos = []
        for v in request.form.getlist("nos"):
            try: nos.append(int(v))
            except ValueError: pass
        n = E.delete_many({"no": {"$in": nos}}).deleted_count if nos else 0
    if n: db.sync_enquiry_counter()       # numbering restarts after the highest remaining enquiry (all deleted -> next is #1)
    flash(f"{n} enquir{'y' if n == 1 else 'ies'} deleted" if n else "Nothing selected - no enquiry deleted")
    return redirect(url_for("admin_enquiries", status=request.form.get("status", ""), q=request.form.get("q", "")))

@app.route("/admin/enquiries/export.csv")
@admin_required
def export_csv():
    rows = find_enquiries()
    cols = ["no", "created", "name", "company", "gst", "uc_code", "portal_access", "reps", "phone", "product", "size", "thickness", "length", "grade", "standard",
            "brand", "qty", "delivery_date", "remarks", "status", "source", "lang", "wa_confirm"]
    out = io.StringIO(); w = csv.writer(out); w.writerow(cols)
    def rowvals(e, it=None):          # one CSV line per product (extra products repeat the enquiry details)
        d = {**e, **(it or {})}
        if it is not None: d["remarks"] = d["wa_confirm"] = ""
        return [d["created"].strftime("%Y-%m-%d %H:%M") if c == "created" and d.get("created") else d.get(c, "") for c in cols]
    for e in rows:
        w.writerow(rowvals(e))
        for it in e.get("more_items") or []: w.writerow(rowvals(e, it))
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=enquiries.csv"})

@app.route("/admin/enquiries/export.pdf")
@admin_required
def export_pdf():
    return Response(pdfgen.listing(find_enquiries()), mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=enquiries.pdf"})

@app.route("/admin/enquiries/<int:no>.pdf")
@admin_required
def enquiry_pdf(no):
    e = database().enquiries.find_one({"no": no}) or abort(404)
    return Response(pdfgen.single(e), mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=enquiry_{no}.pdf"})

# ---------- admin: customers (everyone who started a chat: name, contact, location) ----------
@app.route("/admin/customers")
@admin_required
def admin_customers():
    q, f = request.args.get("q", "").strip(), {}
    if q:
        import re; rx = {"$regex": re.escape(q), "$options": "i"}
        f["$or"] = [{k: rx} for k in ("name", "phone", "company", "gst", "uc_code")]
    rows = list(database().customers.find(f).sort("created", -1))
    for c in rows: c["enq_count"] = database().enquiries.count_documents({"phone": c["phone"]})
    return render_template("admin_customers.html", rows=rows, q=q)

@app.post("/admin/customers/delete")
@admin_required
def delete_customer():       # remove a customer record; their enquiries are KEPT (Enquiries page / PDF / CSV are not touched); the id is posted, not put in the URL, because it is a chat key
    cid = (request.form.get("id") or "").strip()
    c = database().customers.find_one({"_id": cid}) if cid else None
    if c: database().customers.delete_one({"_id": cid}); flash(f"Customer “{c.get('name') or cid}” deleted (their enquiries are kept)")
    else: flash("Customer not found - it may already be deleted")
    return redirect(url_for("admin_customers"))

@app.post("/admin/customers/bulk-delete")
@admin_required
def bulk_delete_customers():       # delete the ticked customers; their enquiries are KEPT
    ids = [i.strip() for i in request.form.getlist("ids") if i.strip()]
    n = database().customers.delete_many({"_id": {"$in": ids}}).deleted_count if ids else 0
    flash(f"{n} customer{'' if n == 1 else 's'} deleted (their enquiries are kept)" if n else "Nothing selected - no customer deleted")
    return redirect(url_for("admin_customers", q=request.form.get("q", "")))

# ---------- admin: job applications + vendor registrations (from the chatbot) ----------
@app.route("/admin/jobs")
@admin_required
def admin_jobs():
    rows = list(database().jobs.find().sort("no", -1))
    reviewed = {r["no"]: job.resume_reviewed(r) for r in rows}      # step 1 status per application (same rule the server enforces)
    return render_template("admin_jobs.html", rows=rows, reviewed=reviewed)

@app.post("/admin/jobs/<int:no>/delete")
@admin_required
def job_delete(no):
    j = database().jobs.find_one({"no": no}) or abort(404)
    if not job.is_closed(j):            # WORKFLOW last step: delete only after the final decision (or the candidate declined)
        flash(f"#{no} cannot be deleted yet - finish the steps first (resume → interview → reply → final decision)."); return redirect(url_for("admin_jobs"))
    database().jobs.delete_one({"no": no}); job.remove_files(no)
    flash(f"Job application #{no} deleted"); return redirect(url_for("admin_jobs"))

@app.post("/admin/jobs/<int:no>/schedule-interview")
@admin_required
def job_schedule_interview(no):
    j = database().jobs.find_one({"no": no}) or abort(404)
    if not job.resume_reviewed(j):
        flash(f"Step 1 pending: please view / download the resume of #{no} before scheduling an interview."); return redirect(url_for("admin_jobs"))
    if j.get("final_status"):
        flash(f"#{no} is already marked {j['final_status']} - the process is closed."); return redirect(url_for("admin_jobs"))
    date = (request.form.get("date") or "").strip()[:20]
    time_ = (request.form.get("time") or "").strip()[:10]
    if not date or not time_:
        flash("Please enter both the interview date and time"); return redirect(url_for("admin_jobs"))
    database().jobs.update_one({"no": no}, {"$set": {
        "interview_date": date, "interview_time": time_, "interview_status": "Scheduled",
        "interview_scheduled_at": db.now_ist(), "interview_scheduled_by": session.get("admin_name")}})
    j = database().jobs.find_one({"no": no})
    accept_url, decline_url = job.interview_links(no, base=site_url())
    st = mailer.start_interview(j, accept_url, decline_url)
    if st == "no-recipient": flash(f"Interview scheduled for #{no}, but this candidate has no email saved - mail not sent.")
    elif st == "off": flash(f"Interview scheduled for #{no}. (Mail notify is switched off in .env - MAIL_NOTIFY=0.)")
    else: flash(f"Interview scheduled for #{no} - mailing the candidate now.")
    return redirect(url_for("admin_jobs"))

@app.post("/admin/jobs/<int:no>/decision")
@admin_required
def job_decision(no):               # WORKFLOW step 4: Selected (only after the candidate accepted the interview) / Rejected (after the resume was reviewed)
    j = database().jobs.find_one({"no": no}) or abort(404)
    res = (request.form.get("result") or "").strip()
    if res not in ("Selected", "Rejected"): abort(400)
    if not job.resume_reviewed(j):
        flash(f"Step 1 pending: view / download the resume of #{no} first."); return redirect(url_for("admin_jobs"))
    if j.get("final_status"):
        flash(f"#{no} is already marked {j['final_status']}."); return redirect(url_for("admin_jobs"))
    if res == "Selected" and j.get("interview_status") != "Accepted":
        flash(f"#{no} can be Selected only after the candidate has ACCEPTED the interview."); return redirect(url_for("admin_jobs"))
    database().jobs.update_one({"no": no}, {"$set": {"final_status": res, "final_at": db.now_ist(), "final_by": session.get("admin_name")}})
    flash(f"Application #{no} marked {res}."); return redirect(url_for("admin_jobs"))

@app.post("/admin/jobs/<int:no>/resend-interview-mail")
@admin_required
def job_resend_interview_mail(no):
    j = database().jobs.find_one({"no": no}) or abort(404)
    accept_url, decline_url = job.interview_links(no, base=site_url())
    ok, note = mailer.send_interview(j, accept_url, decline_url)
    database().jobs.update_one({"no": no}, {"$set": {"interview_mail": "sent" if ok else "failed", "interview_mail_note": note[:400], "interview_mail_at": db.now_ist()}})
    flash(f"Interview mail for #{no}: " + ("sent ✅" if ok else "failed ❌ – " + note))
    return redirect(url_for("admin_jobs"))

# ---------- public: candidate taps Accept / Decline in the interview email (no login, signed token) ----------
@app.get("/job/interview/<int:no>/accept/<token>")
def job_interview_accept(no, token):
    if not job.interview_token_ok(no, "accept", token): abort(404)
    j = database().jobs.find_one({"no": no}) or abort(404)
    if j.get("interview_status") in ("Scheduled", "Declined"):
        database().jobs.update_one({"no": no}, {"$set": {"interview_status": "Accepted", "interview_responded_at": db.now_ist()}})
        j = database().jobs.find_one({"no": no})
    return render_template("job_interview_response.html", ok=True, j=j)

@app.get("/job/interview/<int:no>/decline/<token>")
def job_interview_decline(no, token):
    if not job.interview_token_ok(no, "decline", token): abort(404)
    j = database().jobs.find_one({"no": no}) or abort(404)
    if j.get("interview_status") in ("Scheduled", "Accepted"):
        database().jobs.update_one({"no": no}, {"$set": {"interview_status": "Declined", "interview_responded_at": db.now_ist()}})
        j = database().jobs.find_one({"no": no})
    return render_template("job_interview_response.html", ok=False, j=j)

@app.get("/admin/jobs/<int:no>/form.pdf")
@admin_required
def job_form_pdf(no):               # the filled Job Application Form (same PDF that is mailed to the admins)
    j = database().jobs.find_one({"no": no}) or abort(404)
    return Response(pdfgen.job(j), mimetype="application/pdf", headers={"Content-Disposition": f"inline; filename=Job_Application_Form_{no}.pdf"})

@app.get("/job-resume/<int:no>/<token>")
def job_resume_public(no, token):   # opened from the Preview / Download buttons in the mail & PDF - NO login, but only with the signed token
    if not job.token_ok(no, token): abort(404)
    j = database().jobs.find_one({"no": no}) or abort(404)
    p = job.file_path(j) or abort(404)
    r = send_from_directory(os.path.dirname(p), os.path.basename(p), mimetype="application/pdf", as_attachment=bool(request.args.get("dl")),
                            download_name=f"Resume_{no}_{secure_filename(j.get('name') or 'applicant')}.pdf")
    r.headers["Cache-Control"] = "private, max-age=300"; r.headers["X-Robots-Tag"] = "noindex, nofollow"; return r

@app.get("/admin/jobs/<int:no>/resume")
@admin_required
def job_resume(no):                 # resumes are private: only a logged-in admin can open them
    j = database().jobs.find_one({"no": no}) or abort(404)
    p = job.file_path(j) or abort(404)
    if not j.get("resume_viewed"):      # WORKFLOW step 1: the resume must be opened/downloaded by an admin before anything else
        database().jobs.update_one({"no": no}, {"$set": {"resume_viewed": db.now_ist(), "resume_viewed_by": session.get("admin_name")}})
    r = send_from_directory(os.path.dirname(p), os.path.basename(p), as_attachment=bool(request.args.get("dl")),
                            download_name=f"Resume_{no}_{secure_filename(j.get('name') or 'applicant')}.pdf")
    r.headers["Cache-Control"] = "no-store"; return r

# ---------- admin: vendor registrations (list, full details + office-use block, PDF, documents, CSV) ----------
def find_vendors():
    f, st, q = {}, request.args.get("status", ""), request.args.get("q", "").strip()
    if st: f["status"] = st
    if q:
        import re; rx = {"$regex": re.escape(q), "$options": "i"}
        f["$or"] = [{k: rx} for k in ("firm", "company", "contact", "name", "mobile", "phone", "email", "pan", "gst", "city", "products", "supplies", "vendor_code")]
    return list(database().vendors.find(f).sort("no", -1))

@app.route("/admin/vendors")
@admin_required
def admin_vendors():
    V = database().vendors
    counts = {"all": V.count_documents({}), **{st: V.count_documents({"status": st}) for st in vendor.STATUSES}}
    return render_template("admin_vendors.html", rows=find_vendors(), counts=counts, vn=vendor, status=request.args.get("status", ""), q=request.args.get("q", ""))

@app.route("/admin/vendors/<int:no>")
@admin_required
def admin_vendor(no):
    v = database().vendors.find_one({"no": no}) or abort(404)
    return render_template("admin_vendor.html", v=v, vn=vendor, form=vendor.form())

@app.post("/admin/vendors/<int:no>/office")
@admin_required
def vendor_office(no):
    V = database().vendors; v = V.find_one({"no": no}) or abort(404)
    g = lambda k, n=60: " ".join(request.form.get(k, "").split())[:n]
    code, st = g("vendor_code", 30), request.form.get("status", v.get("status", "New"))
    if st not in vendor.STATUSES: st = v.get("status", "New")
    if code and V.find_one({"vendor_code": code, "no": {"$ne": no}}):
        flash(f"Vendor code {code} is already used by another vendor."); return redirect(url_for("admin_vendor", no=no))
    V.update_one({"no": no}, {"$set": {"vendor_code": code, "verified_by": g("verified_by"), "approved_by": g("approved_by"),
                                       "office_date": g("office_date", 20), "office_note": g("office_note", 500), "status": st}})
    flash("Saved"); return redirect(url_for("admin_vendor", no=no))

@app.route("/admin/vendors/<int:no>.pdf")
@admin_required
def vendor_pdf(no):
    v = database().vendors.find_one({"no": no}) or abort(404)
    return Response(pdfgen.vendor(v), mimetype="application/pdf", headers={"Content-Disposition": f"attachment; filename=Vendor_{no}.pdf"})

@app.route("/admin/vendors/<int:no>/file/<key>")
@admin_required
def vendor_file(no, key):           # uploaded documents are private: only a logged-in admin can open them
    v = database().vendors.find_one({"no": no}) or abort(404)
    p = vendor.file_path(v, key) if key in vendor.FILE_KEYS else None
    if not p: abort(404)
    r = send_from_directory(os.path.dirname(p), os.path.basename(p), as_attachment=bool(request.args.get("dl")),
                            download_name=f"Vendor{no}_{vendor.FILE_LABEL[key].split('/')[0].strip().replace(' ', '_')}{os.path.splitext(p)[1]}")
    r.headers["Cache-Control"] = "no-store"; return r

@app.post("/admin/vendors/<int:no>/delete")
@admin_required
def vendor_delete(no):
    database().vendors.delete_one({"no": no}); vendor.remove_files(no)
    flash(f"Vendor registration #{no} deleted"); return redirect(url_for("admin_vendors"))

@app.route("/admin/vendors/export.csv")
@admin_required
def vendors_csv():
    cols = ["no", "created", "status", "vendor_code", "firm", "constitution", "country", "cstatus", "vtype", "contact", "designation", "address", "city", "state", "pin", "mobile", "landline",
            "email", "website", "year", "pan", "gst", "udyam", "cin", "acc_name", "bank", "acc_no", "ifsc", "acc_type", "branch", "products", "clients", "turnover",
            "pay_terms", "signatory", "sig_desig", "place", "verified_by", "approved_by", "office_date", "source"]
    out = io.StringIO(); w = csv.writer(out); w.writerow(cols + ["documents"])
    for v in find_vendors():
        row = [v["created"].strftime("%Y-%m-%d %H:%M") if c == "created" and v.get("created") else
               {"firm": vendor.firm(v), "contact": vendor.contact(v), "mobile": vendor.mobile(v), "products": vendor.products(v)}.get(c, v.get(c, "")) for c in cols]
        w.writerow(row + [", ".join(vendor.FILE_LABEL[k] for k in vendor.FILE_KEYS if k in (v.get("files") or {}))])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=vendors.csv"})

# ---------- admin: contacts, catalog files, QR, admins ----------
@app.route("/admin/contacts", methods=["GET", "POST"])
@admin_required
def admin_contacts():
    if request.method == "POST":
        f = request.form
        if f.get("delete_id"):
            database().contacts.delete_one({"_id": ObjectId(f["delete_id"])})
            flash("Deleted")
        else:
            d = {k: f.get(k, "").strip() for k in ("department", "name", "designation", "phone", "email", "direct_line")}
            d["department"] = d["department"].upper()
            if f.get("id"): database().contacts.update_one({"_id": ObjectId(f["id"])}, {"$set": d})
            else: database().contacts.insert_one(d)
            flash("Saved")
    groups = {}                                    # department -> contacts (department-wise view)
    for r in ser(database().contacts.find().sort("_id", 1)):
        groups.setdefault((r.get("department") or "OTHER").strip().upper(), []).append(r)
    return render_template("admin_contacts.html", groups=groups, depts=list(groups.keys()))

DOC_CATS = [("catalogue", "Company Catalogue"), ("datasheet", "Technical Datasheet / Size-Thk / Weight chart"),
            ("certificate", "Distribution Certificate"), ("awards", "Awards & Achievements"),
            ("documents", "\U0001F4C4 Documents (shown under Documents in chat)"),
            ("godown", "\U0001F3ED Godown Images (shown in Gallery -> Godown)"), ("office", "\U0001F3E2 Office Images (shown in Gallery -> Office)")]
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
IMG_CATS = ("godown", "office")

def _doc_rows(cat):
    """Everything the chat shows for one category. Files uploaded from this page come first (newest on top), then files kept in the catalog/<cat>/ folder."""
    up, fo, folder, hid = [], [], os.path.join(bot.CATALOG_DIR, cat), bot.hidden_folder_files(cat)
    for d in database().documents.find({"category": cat}).sort("_id", -1):
        fn = d.get("filename", "")
        up.append({"src": "db", "key": str(d["_id"]), "title": d.get("title") or fn, "filename": fn, "url": f"/files/{quote(fn)}",
                   "missing": not os.path.isfile(os.path.join(UPLOADS, fn)), "is_img": fn.lower().endswith(IMG_EXT)})
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.startswith(".") or fn in hid or not os.path.isfile(os.path.join(folder, fn)) or fn.lower().endswith((".txt", ".md")): continue
            title = re.sub(r"^\d+\s+", "", os.path.splitext(fn)[0].replace("_", " ").replace("-", " ").strip())
            fo.append({"src": "folder", "key": fn, "title": title, "filename": fn, "url": f"/catalog-files/{cat}/{quote(fn)}", "is_img": fn.lower().endswith(IMG_EXT)})
    return up + fo

def _safe_upload_name(orig):
    """secure_filename() can return '' / only an extension for names such as Hindi ones - never silently drop the file; never overwrite an older one."""
    name = secure_filename(orig or ""); base, ext = os.path.splitext(name)
    if not base:
        ext = ext or os.path.splitext(orig or "")[1].lower()
        base = "upload_" + time.strftime("%Y%m%d_%H%M%S")
    name = base + ext
    if os.path.exists(os.path.join(UPLOADS, name)): name = f"{base}_{int(time.time())}{ext}"
    return name

@app.errorhandler(413)
def too_big(e):
    if request.path.startswith("/admin/documents") and "admin_id" in session:
        flash("Upload failed: files are too large (limit 60 MB per upload). Upload fewer photos at a time.")
        return redirect(url_for("admin_docs"))
    return ("File too large", 413)

@app.route("/admin/documents", methods=["GET", "POST"])
@admin_required
def admin_docs():
    cat = request.values.get("category") or request.args.get("cat") or "catalogue"
    if cat not in dict(DOC_CATS): cat = "catalogue"
    if request.method == "POST":
        files = [f for f in request.files.getlist("file") if f and (f.filename or "").strip()]
        title_in = request.form.get("title", "").strip(); n_ok = n_bad = 0
        if not files: flash("Please choose a file to upload")
        for f in files:
            if cat in IMG_CATS and not (f.filename or "").lower().endswith(IMG_EXT): n_bad += 1; continue      # godown / office accept pictures only
            os.makedirs(UPLOADS, exist_ok=True)
            name = _safe_upload_name(f.filename)
            f.save(os.path.join(UPLOADS, name))
            title = title_in if (title_in and len(files) == 1) else os.path.splitext(name)[0].replace("_", " ")
            database().documents.insert_one({"category": cat, "title": title, "filename": name}); n_ok += 1
        if n_ok: flash(f"Uploaded {n_ok} file" + ("" if n_ok == 1 else "s"))
        if n_bad: flash(f"{n_bad} file(s) skipped - only images (jpg, png, webp, gif) are allowed here")
        return redirect(url_for("admin_docs", cat=cat))
    return render_template("admin_docs.html", docs=_doc_rows(cat), cat=cat, cats=DOC_CATS, counts={k: len(_doc_rows(k)) for k, _ in DOC_CATS})

@app.post("/admin/documents/delete")
@admin_required
def delete_doc():
    cat, src, key = request.form.get("cat", ""), request.form.get("src", ""), request.form.get("key", "")
    if cat not in dict(DOC_CATS): return redirect(url_for("admin_docs"))
    if src == "db":
        d = database().documents.find_one({"_id": ObjectId(key)})
        if d:
            database().documents.delete_one({"_id": d["_id"]})
            fn = d.get("filename", "")
            if fn and not database().documents.find_one({"filename": fn}):      # remove the file too, unless another entry still uses it
                try: os.remove(os.path.join(UPLOADS, secure_filename(fn)))
                except OSError: pass
    elif src == "folder":
        try: os.remove(os.path.join(bot.CATALOG_DIR, secure_filename(cat), secure_filename(key)))
        except OSError: pass
        if not database().hidden_files.find_one({"category": cat, "filename": key}):      # remember it, so a redeploy / git pull cannot bring the file back
            database().hidden_files.insert_one({"category": cat, "filename": key})
    flash("Deleted")
    return redirect(url_for("admin_docs", cat=cat))

@app.route("/admin/qr")
@admin_required
def admin_qr():
    return render_template("admin_qr.html", target=qr_target())

import base64, hashlib
def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("admin-pw:" + app.secret_key).encode()).digest()))

def _enc_pw(p):
    """Encrypted copy of the password so the admin panel can show it (needs SECRET_KEY to read it back)."""
    return _fernet().encrypt(p.encode()).decode()

def _dec_pw(tok):
    try: return _fernet().decrypt(tok.encode()).decode() if tok else None
    except Exception: return None

import re as _re
_EMAIL_RE = _re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}")
_USER_RE = _re.compile(r"[a-z0-9][a-z0-9._-]{2,29}")
MIN_PASSWORD = 6

def _active_admin_count(exclude_id=None):
    q = {"active": True}
    if exclude_id: q["_id"] = {"$ne": ObjectId(exclude_id)}
    return database().admins.count_documents(q)

def _check_admin_fields(f, admin_id=None, need_password=True):
    """Validate the add / edit admin form. Returns (clean_dict, error_message)."""
    A = database().admins
    name = f.get("name", "").strip()
    username = f.get("username", "").strip().lower()
    digits = "".join(ch for ch in f.get("phone", "") if ch.isdigit())
    email = f.get("email", "").strip()
    password = f.get("password", "")
    if len(name) < 2: return None, "Please enter the admin's name"
    if not _USER_RE.fullmatch(username):
        return None, "Username must be 3-30 characters: letters, numbers, dot, dash or underscore"
    if len(digits) != 10: return None, "Enter a valid 10-digit mobile number"
    if email and not _EMAIL_RE.fullmatch(email): return None, "Enter a valid email address"
    if (need_password or password) and len(password) < MIN_PASSWORD:
        return None, f"Password must be at least {MIN_PASSWORD} characters"
    phone = norm(digits)
    me = {"_id": {"$ne": ObjectId(admin_id)}} if admin_id else {}
    if A.find_one({**me, "username": username}): return None, f"Username '{username}' is already taken"
    if A.find_one({**me, "phone": phone}): return None, "This mobile number is already used by another admin"
    return dict(name=name, username=username, phone=phone, email=email, password=password), None

@app.route("/admin/admins", methods=["GET", "POST"])
@admin_required
def admin_admins():
    A = database().admins
    if request.method == "POST":
        f = request.form; action = f.get("action", "add")
        if action == "edit":                                     # name, username, mobile, email and (optional) new password
            try: ObjectId(f.get("id", ""))
            except Exception: flash("Admin not found"); return redirect(url_for("admin_admins"))
            d, err = _check_admin_fields(f, admin_id=f["id"], need_password=False)
            if err: flash(err)
            else:
                upd = {"name": d["name"], "username": d["username"], "phone": d["phone"], "email": d["email"]}
                if d["password"]:
                    upd["password_hash"] = generate_password_hash(d["password"]); upd["password_enc"] = _enc_pw(d["password"]); upd["pw_changed"] = db.now_ist()
                A.update_one({"_id": ObjectId(f["id"])}, {"$set": upd})
                if f["id"] == session["admin_id"]: session["admin_name"] = d["name"]
                flash("Admin updated" + (" and password reset" if d["password"] else ""))
        elif action == "email":                                    # kept for old forms / bookmarks
            email = f.get("email", "").strip()
            if email and not _EMAIL_RE.fullmatch(email): flash("Enter a valid email address")
            else:
                A.update_one({"_id": ObjectId(f["id"])}, {"$set": {"email": email}})
                flash("Email saved" if email else "Email removed - this admin will stop getting enquiry PDFs by mail")
        else:                                                      # add admin
            d, err = _check_admin_fields(f)
            if err: flash(err)
            else:
                try:
                    A.insert_one({"name": d["name"], "username": d["username"], "phone": d["phone"], "email": d["email"],
                                  "password_hash": generate_password_hash(d["password"]), "password_enc": _enc_pw(d["password"]),
                                  "active": True, "job_notify": False, "sales_notify": False, "created": db.now_ist(), "pw_changed": db.now_ist()})
                    flash(f"Admin '{d['name']}' added")
                except Exception: flash("This username or mobile number already exists")
        return redirect(url_for("admin_admins"))
    rows = ser(A.find({}, {"password_hash": 0}).sort("created", 1))
    for r in rows: r["pw_plain"] = _dec_pw(r.pop("password_enc", None))
    stats = dict(total=len(rows), active=sum(1 for r in rows if r.get("active", True)),
                 disabled=sum(1 for r in rows if not r.get("active", True)),
                 job=sum(1 for r in rows if r.get("job_notify")), sales=sum(1 for r in rows if r.get("sales_notify")))
    return render_template("admin_admins.html", admins=rows, me=session["admin_id"], stats=stats, min_pw=MIN_PASSWORD)

@app.post("/admin/admins/<id>/toggle")
@admin_required
def toggle_admin(id):
    A = database().admins
    a = A.find_one({"_id": ObjectId(id)})
    if not a: flash("Admin not found")
    elif id == session["admin_id"]: flash("You can't disable the account you're logged in as")
    elif a.get("active", True) and _active_admin_count(exclude_id=id) == 0: flash("At least one active admin is required")
    else:
        A.update_one({"_id": a["_id"]}, {"$set": {"active": not a.get("active", True)}})
        flash(f"{a['name']} " + ("enabled" if not a.get("active", True) else "disabled"))
    return redirect(url_for("admin_admins"))

@app.post("/admin/admins/<id>/toggle-job")
@admin_required
def toggle_admin_job(id):
    """Links / unlinks this admin to receive Job Application emails (admin_jobs page, Admin -> Admins)."""
    a = database().admins.find_one({"_id": ObjectId(id)})
    if a and not a.get("email"): flash("Add an email for this admin first")
    elif a: database().admins.update_one({"_id": a["_id"]}, {"$set": {"job_notify": not a.get("job_notify", False)}})
    return redirect(url_for("admin_admins"))

@app.post("/admin/admins/<id>/toggle-sales")
@admin_required
def toggle_admin_sales(id):
    """Links / unlinks this admin as a SALES person: gets the 'product available? + write price' mail for every enquiry."""
    a = database().admins.find_one({"_id": ObjectId(id)})
    if a and not a.get("email"): flash("Add an email for this admin first")
    elif a:
        on = not a.get("sales_notify", False)
        database().admins.update_one({"_id": a["_id"]}, {"$set": {"sales_notify": on}})
        flash(f"{a['name']}: sales price mails " + ("ON - will get every new enquiry's stock check + price link" if on else "OFF"))
    return redirect(url_for("admin_admins"))

@app.post("/admin/admins/<id>/delete")
@admin_required
def delete_admin(id):
    A = database().admins
    a = A.find_one({"_id": ObjectId(id)})
    if not a: flash("Admin not found")
    elif id == session["admin_id"]: flash("You can't delete the admin account you're logged in as")
    elif a.get("active", True) and _active_admin_count(exclude_id=id) == 0: flash("At least one active admin is required")
    else:
        A.delete_one({"_id": a["_id"]})
        flash(f"Admin '{a['name']}' deleted")
    return redirect(url_for("admin_admins"))

def _backfill_env_admin_password():
    """The default admin (ADMIN_PHONE in .env) - if their password is still the .env ADMIN_PASSWORD, save it so it shows in the panel."""
    try:
        pw = os.getenv("ADMIN_PASSWORD", "admin123")
        a = database().admins.find_one({"phone": norm(os.getenv("ADMIN_PHONE", "9930988307"))})
        if a and not a.get("password_enc") and check_password_hash(a["password_hash"], pw):
            database().admins.update_one({"_id": a["_id"]}, {"$set": {"password_enc": _enc_pw(pw)}})
    except Exception as ex: print("backfill admin password:", ex)
_backfill_env_admin_password()
_poller = {"on": False}
@app.before_request
def _start_sales_poller_once():      # started inside each gunicorn worker (threads do not survive preload fork); a DB lock keeps only one worker polling
    if not _poller["on"]:
        _poller["on"] = True
        sales_quote.start_poller()   # optional: sales person can also REPLY to the mail with the price (SALES_IMAP_POLL=1)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG", "0") == "1")
