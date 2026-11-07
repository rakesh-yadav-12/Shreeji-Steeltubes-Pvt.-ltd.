"""Conversation flow:  Start -> Hi/Welcome -> Home -> Existing user?
      Yes -> Customer Details Form (or About Us)          No -> About Us -> Type of Pipe -> Godown -> Brands -> Layers -> Customer Details Form
      Customer Details Form (customer + representative details) -> Enquiry Form -> Submit -> Confirmation
Web chat shows real FORMS; WhatsApp asks the same fields one by one.   Catalog & Contacts stay available from Home."""
import os, re, json, secrets
from urllib.parse import quote_plus, quote
from datetime import datetime, timedelta
import options as OPT
import about_fetch, i18n, confirm, gstverify, mailer, sheet_quote, sales_quote
from db import database, get_state, set_state, next_no, now_ist, norm, get_lang, set_lang, set_utype
from whatsapp import send_text, send_document, send_image, send_video
from whatsapp import LANG as _LANG          # 'en' / 'hi' for the conversation being handled

# Product list as shown to the customer.  A [heading, [sub-products]] entry is a group: the heading is NOT selectable, only its sub-products are.
PRODUCT_GROUPS = [["MS ERW Pipe", ["MS Round Pipe", "MS Square Hollow Section", "MS Rectangle Hollow Section"]],
                  ["GI ERW Pipe", ["GI Round Pipe", "GI Square Hollow Section", "GI Rectangle Hollow Section"]],
                  ["GP Pipe (Pre-Galvanized)", ["GP Square Hollow Section", "GP Rectangle Hollow Section"]],
                  ["Large Dia Pipes", ["Large Diameter Round Pipe"]],
                  "Spiral Welded Pipes", "Seamless Pipe"]
PRODUCTS = [p for g in PRODUCT_GROUPS for p in (g[1] if isinstance(g, list) else [g])]      # every product that can be SAVED on an enquiry (sub-products, not the heading)
PARENTS = [g[0] if isinstance(g, list) else g for g in PRODUCT_GROUPS]                       # first dropdown: MS ERW Pipe, GI ERW Pipe ...
SUBS = {g[0]: g[1] for g in PRODUCT_GROUPS if isinstance(g, list)}                           # choosing "MS ERW Pipe" opens its 3 sub-products

def product_lines(num=False, bullet="• "):
    """Grouped product list as text lines.  num=True -> WhatsApp numbering (numbers match PRODUCTS order)."""
    out, n = [], 0
    for g in PRODUCT_GROUPS:
        if isinstance(g, str):
            n += 1; out.append(f"{n}. {g}" if num else bullet + g)
        else:
            out.append(f"*{g[0]}*" if num else bullet + g[0])
            for s in g[1]:
                n += 1; out.append(f"   {n}. {s}" if num else "    – " + s)
    return out
CATALOG = ["Company Catalogue", "Technical Datasheet / Size-Thickness Range / Weight Chart",
           "Distribution Certificate", "Awards & Achievements", "📄 Documents"]
CAT_KEYS = ["catalogue", "datasheet", "certificate", "awards", "documents"]
GREET = ("hi",)            # only when the customer types Hi
HERE = os.path.dirname(os.path.abspath(__file__))

def _digits(x): return re.sub(r"\D", "", str(x or ""))

def company_phones():
    """[(department, person, 10-digit number)] for EVERY department - options.COMPANY_PHONES, else Admin -> Contacts."""
    rows = [(r[0], (r[2] if len(r) > 2 else ""), r[1]) for r in OPT.COMPANY_PHONES] or \
           [(r.get("department", "Call"), r.get("name"), r.get("phone")) for r in database().contacts.find()]
    out = []
    for dept, who, num in rows:
        d = _digits(num)[-10:]
        who = "" if who in (None, "", "-", "Update in admin panel") else who
        if len(d) == 10 and (dept, d) not in [(x[0], x[2]) for x in out]: out.append((dept, who, d))
    return out

def _clean(v):
    v = str(v or "").strip()
    return "" if v in ("-", "--") or v.lower() == "update in admin panel" else v

def contact_rows():
    """Admin -> Contacts as a flat list grouped department by department (first-added department first)."""
    groups = {}
    for r in database().contacts.find().sort("_id", 1):
        groups.setdefault((_clean(r.get("department")) or "OTHER").upper(), []).append(r)
    out = []
    for dept, people in groups.items():
        for r in people:
            d = _digits(r.get("phone"))[-10:]
            out.append({"dept": dept, "department": dept, "name": _clean(r.get("name")), "desig": _clean(r.get("designation")),
                        "designation": _clean(r.get("designation")), "phone": _clean(r.get("phone")), "direct": _clean(r.get("direct_line")),
                        "email": _clean(r.get("email")), "tel": ("tel:+91" + d) if len(d) == 10 else ""})
    return out

def call_lines(calls):
    return "\n".join(f"*{dept}*{' – ' + who if who else ''}: +91 {n[:5]} {n[5:]}" for dept, who, n in calls)

def call_links(calls):
    """One entry per department: (Department, 'tel:+91..', person) - the web chat shows them inside ONE 'Call' tab."""
    return [(dept, "tel:+91" + n, who) for dept, who, n in calls]

def visit_card(to, phone):
    """Advert-style 'Visit Us' card: address + Google Maps link. (Department call numbers are only in Contact Details.)"""
    maps = OPT.MAPS_LINK or "https://www.google.com/maps/search/?api=1&query=" + quote_plus(getattr(OPT, "COMPANY_MAP_QUERY", "") or OPT.COMPANY_ADDRESS)
    head = f"📍 *Visit Us*\n{OPT.COMPANY_ADDRESS}"
    if phone is None:       # web chat: Map button
        return send_text(to, head, links=[("🗺️ Open in Google Maps", maps)])
    return send_text(to, head + f"\n\n🗺️ Find us on map:\n{maps}")

CATALOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog")      # drop files in catalog/<catalogue|datasheet|certificate|awards>/
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

HIDDEN_DOCS = {"shreeji company catalogue"}      # documents that must never be shown (matched on file name / title, ignoring case, _ and -) - add a name here to hide any card
def _hidden(*names): return any(re.sub(r"[\s_\-]+", " ", os.path.splitext(n or "")[0]).strip().lower() in HIDDEN_DOCS or re.sub(r"[\s_\-]+", " ", n or "").strip().lower() in HIDDEN_DOCS for n in names)

# Distribution Certificate: the first 19 old files must never show, even if they are still sitting on the server (only newer ones from no. 20 on are shown)
HIDDEN_FOLDER_FILES = {"certificate": set(['01_Jindal_Dealership.pdf', '02_Hitech_Saw_Dealership.pdf', '03_ISO_9001_2015_Certificate.pdf', '04_Hitech_Saw_Highest_Lifting_Award.pdf', '05_CEO_Insights_Top_10_Leaders_2024.pdf', '06_Asian_Tubes_Dealership.pdf', '07_Hitech_Pipes_Certificate_of_Partnership.pdf', '08_Jindal_Star_Dealership.pdf', '09_Maharashtra_Seamless_Dealership.pdf', '10_Tata_Steel_Dealership.pdf', '11_Asian_Tubes_Dealership_Certificate.pdf', '12_Tata_Steel_Highest_Sales_Congratulations.pdf', '13_HiTech_Pipes_Certificate_of_Partnership_2026-27.pdf', '14_MSL_Jindal_Authorized_Distributor_2025-26.pdf', '15_Tata_Structura_Distributor_Appointment_Letter.pdf', '16_CEO_Insights_Certificate_of_Recognition.pdf', '17_CEO_Insights_Ronak_Modi_Interview.pdf', '18_CEO_Insights_Shreeji_SteelTubes_Reprint.pdf', '19_CEO_Insights_Leaders_Mining_Metals_Full_Magazine.pdf'])}
def hidden_folder_files(cat):
    """File names in catalog/<cat>/ that must not be shown: the built-in list above + everything an admin deleted (kept in DB so a redeploy cannot bring it back)."""
    return set(HIDDEN_FOLDER_FILES.get(cat, ())) | {d.get("filename") for d in database().hidden_files.find({"category": cat})}

def catalog_docs(cat):
    """[(url_path, filename, title)] = files in catalog/<cat>/ folder  +  files uploaded in Admin -> Documents (only if the file really exists)."""
    out, seen = [], set()
    folder = os.path.join(CATALOG_DIR, cat); hid = hidden_folder_files(cat)
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.startswith(".") or not os.path.isfile(os.path.join(folder, fn)) or fn.lower().endswith((".txt", ".md")): continue
            if _hidden(fn) or fn in hid: continue
            out.append((f"/catalog-files/{cat}/{quote(fn)}", fn, re.sub(r"^\d+\s+", "", os.path.splitext(fn)[0].replace("_", " ").replace("-", " ").strip())))   # leading "01_" only sets the order; seen.add(fn)
    for d in database().documents.find({"category": cat}):
        fn = d.get("filename", "")
        if fn and fn not in seen and not _hidden(fn, d.get("title")) and os.path.isfile(os.path.join(UPLOAD_DIR, fn)):
            out.append((f"/files/{quote(fn)}", fn, d.get("title") or fn)); seen.add(fn)
    return out

def ask_catalog(to, phone, prefix=""):
    if phone is None:
        return send_text(to, prefix + "*Catalog & Technical Details*\nChoose one 👇",
                         chips=[(c, str(n)) for n, c in enumerate(CATALOG, 1)] + [HOME], ph="Tap an option above…", lt="Select catalogue")
    return send_text(to, prefix + menu_list("*Catalog & Technical Details*", CATALOG))

def ask_doclist(key, to, phone, prefix=""):
    """'Documents' section: lists every document the admin has added (Admin panel -> Documents -> category 'Documents')."""
    docs = catalog_docs("documents")
    if not docs:
        set_state(key, "CATALOG", {})
        return ask_catalog(to, phone, prefix + "ℹ️ No documents have been added yet. Our team will add them soon.\n\n")
    title = prefix + "*Documents*\nTap the document you want to receive:"
    if phone is None:
        return send_text(to, title, chips=[(t_, str(n)) for n, (_, _, t_) in enumerate(docs, 1)] + [("⬅ Back", "back"), HOME],
                         ph="Tap a document above…", lt="Select document")
    return send_text(to, prefix + menu_list("*Documents*", [t_ for _, _, t_ in docs]).replace("0 = main menu", "back = catalog menu • 0 = main menu"))

def menu_list(title, items):
    return title + "\n\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(items)) + "\n\n_Reply with a number. 0 = main menu_"

def contact_line(doc):
    ph = str(doc.get("phone") or "")
    return f"Our team will call you shortly on *{fmt_phone(ph)}*." if len(ph) >= 10 and ph != "-" else "Our team will contact you shortly."

def fmt_phone(n):
    n = str(n)
    return f"+91 {n[2:7]} {n[7:]}" if len(n) == 12 and n.startswith("91") else "+" + n



FORM_TAG = "@@FORM@@"
HOME = ("🏠 Main menu", "menu")
USER_ITEMS = [("✅ Existing Customer", "u:exist"), ("🆕 New Customer", "u:new"), ("💼 Join our Team", "s:jobs")]   # shown right after Hi (Join our Team -> Job Application form)
HOME_ITEMS = USER_ITEMS                                            # after Hi: Existing Customer / New User / Join our Team
import contextvars
KEY = contextvars.ContextVar("key", default="")          # conversation key of the message being handled
ABOUT_RE = re.compile(r"\babout\s*-?\s*us\b|^(about|aboutus|about company|company|company profile|company info)$")
GST_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


 # WhatsApp needs public links
def base_url(phone): return os.getenv("PUBLIC_URL", "").rstrip("/") if phone else ""     

# Home
def welcome(to, phone, cust=None, greet=False):
    name = (cust or {}).get("name")
    head = (f"Welcome back, *{name}*! 🙏" if name else "Welcome to *Shreeji Steeltubes Pvt Ltd* 🙏\n_House of Quality Steel Tubes_")
    if phone is not None: head += "\n\n🌐 _Type *hindi* for Hindi • *english* for English_"      # WhatsApp has no header button - tell how to switch
    if phone is None:       # web chat: NO welcome bubble - on "Hi" the New User / Existing Customer popup opens straight away
        return nav(to, phone, "Select user type", HOME_ITEMS, home=False, lt="Select user type", popup="user")
    return nav(to, phone, head, HOME_ITEMS, home=False, lt="Select user type")

def ask_existing(to, phone, cust):
    who = f", *{cust['name']}*" if cust and cust.get("name") else ""
    text = f"Welcome back{who}! 🙏\nWhat would you like to do?"
    if phone is None:
        return send_text(to, text, chips=[("📝 Customer Details Form", "details"), ("ℹ️ About Us", "about"), HOME], lt="Select action")
    return send_text(to, text + "\n\n1. Customer Details Form\n2. About Us\n\n_0 = main menu_")

#  New-user information steps
def info_step(to, phone, i):
    steps = OPT.FLOW_INFO; st = steps[i]; last = i == len(steps) - 1
    text = st["text"]
    if st.get("list"):
        text += "\n" + "\n".join(product_lines() if st["list"] == "PRODUCTS" else ["• " + x for x in OPT.BRANDS])
    imgs = [OPT.INTRO_IMAGES[k - 1] for k in st.get("images", []) if 0 < k <= len(OPT.INTRO_IMAGES)]
    vid = ""
    if st.get("video") and OPT.INTRO_VIDEO and (OPT.INTRO_VIDEO.startswith("http") or os.path.exists(os.path.join(HERE, OPT.INTRO_VIDEO.lstrip("/")))):
        vid = OPT.INTRO_VIDEO
    nxt = ("📝 Fill Customer Details ➡", "next") if last else ("Next ➡", "next")
    chips = [nxt] + ([] if last else [("⏭ Skip to Details Form", "skip")]) + ([("⬅ Back", "back")] if i else [])
    if phone is None:
        kw = dict(gallery=[{"img": u, "cap": c} for u, c in imgs], poster=imgs[0][0]) if imgs else {}
        if vid: kw["video"] = vid
        return send_text(to, text, chips=chips, progress=[i + 1, len(steps), st["title"]], ph="Tap Next ➡ to continue…", lt="Select next step", **kw)
    b = base_url(phone); url = lambda u: u if u.startswith("http") else b + u
    for u, c in imgs: send_image(to, url(u), c)
    if vid: send_video(to, url(vid), "Shreeji SteelTubes – Company Introduction")
    return send_text(to, f"*{st['title']}* ({i + 1}/{len(steps)})\n{text}\n\n_Reply *next* to continue • *skip* = go to the form • *back*_")

#  Forms (schema used for the web form AND the WhatsApp question-by-question flow)
def F(name, label, type="text", req=False, ph="", options=None, val="", **kw):
    d = dict(name=name, label=label, type=type, req=req, ph=ph, val=val or ""); d.update(kw)
    if options: d["options"] = options
    return d

def customer_form(v=None, errs=None):
    v, errs = v or {}, errs or {}
    sec1 = [F("name", "Customer Name", req=True, ph="Full name"),
            F("company", "Company / Firm Name", req=True, ph="Firm name"),
            F("gst", "GST Number", ph="e.g. 27ABCDE1234F1Z0", upper=True, maxlen=15),
            F("uc_code", "UC Code", ph="Your UC code (if any)"),
            F("portal_access", "Portal Access", "select", options=["Yes", "No"])]
    sec2 = []
    for k, lab in OPT.REPRESENTATIVES:
        sec2 += [F(f"{k}_name", f"{lab} – Name", ph="Name"), F(f"{k}_mobile", f"{lab} – Mobile No.", "tel", ph="10-digit mobile", maxlen=14)]
    for s in (sec1, sec2):
        for f in s: f["val"] = v.get(f["name"], f["val"]); f["err"] = errs.get(f["name"], "")
    return {"id": "customer", "title": "📝Customer Details Form", "submit": "Save & Continue ➡",
            "note": "Please fill in your details. Fields marked * are required.",
            "sections": [{"title": "Customer Details", "fields": sec1},
                         {"title": "Representative Details  (add at least one mobile number)", "fields": sec2}]}

def page_customer_fields(mode="new"):
    """'Your Details' block shown at the top of the web Enquiry page when this visitor has no saved customer yet.
    mode 'exist' : UC code only - the page fetches name / company / mobile / email saved when the customer first registered.
    mode 'new'   : name, company, GST (verified on the GST portal) - the UC code is generated automatically."""
    if mode == "exist":
        return [F("c_uc", "UC Code / GST Number", ph="Enter your UC code or GST number", upper=True, maxlen=15),
                F("c_name", "Your Name", ph="Filled automatically", readonly=True),
                F("c_company", "Company / Firm Name", ph="Filled automatically", readonly=True),
                F("c_mobile", "Mobile No.", "tel", ph="Filled automatically", maxlen=14),
                F("c_email", "Email", ph="Filled automatically")]
    return [F("c_name", "Your Name", req=True, ph="Full name"),
            F("c_company", "Company / Firm Name", req=True, ph="Company or firm name"),
            F("c_mobile", "Contact No.", "tel", True, ph="10-digit mobile", maxlen=14),
            F("c_email", "Email", ph="you@example.com"),
            F("c_gst", "GST Number", ph="e.g. 27ABCDE1234F1Z0", upper=True, maxlen=15),
            F("c_uc", "UC Code", ph="Auto-generated from GST", readonly=True)]

def page_customer_vals(vals):
    """Enquiry-page 'Your Details' values -> the keys validate_customer / the customer form expect."""
    r0 = OPT.REPRESENTATIVES[0][0]
    return {"name": vals.get("c_name"), "company": vals.get("c_company"), "email": vals.get("c_email"), "uc_code": vals.get("c_uc"), "gst": vals.get("c_gst"),
            f"{r0}_name": vals.get("c_name"), f"{r0}_mobile": vals.get("c_mobile")}

def page_customer_errs(errs):
    r0 = OPT.REPRESENTATIVES[0][0]
    m = {"name": "c_name", "company": "c_company", "email": "c_email", "gst": "c_gst", "uc_code": "c_uc", f"{r0}_mobile": "c_mobile"}
    return {m.get(k, k): v for k, v in (errs or {}).items()}

UNITS = ["Ton", "Mtr", "Kg"]      # unit of the Quantity (saved together with it, e.g. "5 Ton", so admin / PDF / Excel / WhatsApp keep working)

def enquiry_form(v=None, errs=None):
    v, errs = v or {}, errs or {}
    f = [F("product", "Product", "select", True, options=PARENTS, ph="Select product", subs=SUBS),
         F("size", "Size / NB / OD", req=True, ph="e.g. 50 NB or 60.3 mm OD"),
         F("thickness", "Thickness / Schedule", req=True, ph="e.g. 3.2 mm or Sch 40"),
         F("std_grade", "Standard & Grade", ph="Select or type (e.g. IS 1161 - YST 240)", lists=OPT.STD_GRADE_LISTS, depends="product"),
         F("length", "Length", "select", True, options=["6 m", "12 m", "Other"], ph="Select length", other="Type length (e.g. 8 m / Random)"),
         F("brand", "Brand Preference", "select", options=list(OPT.BRANDS) + ["Other"], ph="Select brand", other="Type brand name",
           by_product={k: list(v) + ["Other"] for k, v in OPT.BRANDS_BY_PRODUCT.items()}),
         F("qty", "Quantity", req=True, ph="e.g. 5"),
         F("unit", "Unit", "select", True, options=UNITS, ph="Select"),
         F("delivery_date", "Delivery Date", "date", immediate="Immediate"),
         F("remarks", "Remarks / Special requirement", "textarea", ph="Anything else we should know?")]
    for x in f: x["val"] = v.get(x["name"], x["val"]); x["err"] = errs.get(x["name"], "")
    return {"id": "enquiry", "title": "📋 Product Enquiry Form", "submit": "Submit Enquiry ✅",
            "note": "Tell us what you need. Fields marked * are required.",
            "sections": [{"title": "Product Requirement", "fields": f}]}

def job_form(v=None, errs=None):
    v, errs = v or {}, errs or {}
    f = [F("name", "Full Name", req=True, ph="Your name"), F("phone", "Mobile No.", "tel", True, ph="10-digit mobile", maxlen=14),
         F("email", "Email", ph="you@example.com"), F("position", "Position applying for", "select", True, options=OPT.JOB_POSITIONS, ph="Select position"),
         F("qualification", "Qualification", ph="e.g. B.Com"), F("experience", "Experience", ph="e.g. 3 years"),
         F("city", "Current City", ph="City"), F("note", "About you / resume link", "textarea", ph="Short note or Google Drive link to your resume")]
    for x in f: x["val"] = v.get(x["name"], ""); x["err"] = errs.get(x["name"], "")
    return {"id": "job", "title": "💼 Job Application Form", "submit": "Submit Application ✅", "note": "Fields marked * are required.", "sections": [{"title": "Application", "fields": f}]}

def vendor_form(v=None, errs=None):
    v, errs = v or {}, errs or {}
    f = [F("company", "Company / Firm Name", req=True, ph="Firm name"), F("name", "Contact Person", req=True, ph="Name"),
         F("phone", "Mobile No.", "tel", True, ph="10-digit mobile", maxlen=14), F("email", "Email", ph="you@example.com"),
         F("gst", "GST Number", ph="e.g. 27ABCDE1234F1Z0", upper=True, maxlen=15), F("city", "City / Address", ph="City"),
         F("supplies", "Products / Services you supply", "textarea", True, ph="e.g. MS pipes, transport, coating"), F("years", "Years in business", ph="e.g. 10")]
    for x in f: x["val"] = v.get(x["name"], ""); x["err"] = errs.get(x["name"], "")
    return {"id": "vendor", "title": "🤝 Vendor Registration", "submit": "Register ✅", "note": "Fields marked * are required.", "sections": [{"title": "Vendor Details", "fields": f}]}

def get_form(fid, v=None, errs=None):
    return {"customer": customer_form, "enquiry": enquiry_form, "job": job_form, "vendor": vendor_form}[fid](v, errs)

def simple_submit(key, to, phone, fid, vals):
    """Job application / vendor registration: validate, save in MongoDB (collections jobs / vendors)."""
    form = get_form(fid); c = {f["name"]: _c(vals.get(f["name"]), 500 if f["type"] == "textarea" else 120) for f in flat(form)}; errs = {}
    for f in flat(form):
        if f["req"] and not c[f["name"]]: errs[f["name"]] = "This field is required"
    c["phone"] = mobile10(c["phone"]) or c["phone"]
    if c["phone"] and not mobile10(c["phone"]): errs["phone"] = "Enter a valid 10-digit mobile number"
    if c.get("gst"):
        c["gst"] = c["gst"].upper().replace(" ", "")
        if not GST_RE.match(c["gst"]): errs["gst"] = "Invalid GST number"
    if errs: return errs
    no = next_no(fid); c.update(no=no, source="whatsapp" if phone else "web", created=now_ist(), status="New")
    database()["jobs" if fid == "job" else "vendors"].insert_one(c)
    n = os.getenv("NOTIFY_NUMBER")
    if n: send_text(n, f"New {'job application' if fid == 'job' else 'vendor registration'} #{no}: {c['name']} {c['phone']}")
    set_state(key, "DONE", {})
    msg = "✅ *Application submitted!* Our HR team will contact you if your profile matches." if fid == "job" else "✅ *Vendor registration received!* Our team will get in touch with you."
    items = [("📋 Product Enquiry Form", "s:enquiry"), ("📞 Contact Us", "s:contact")] if fid == "job" else [("📋 Request For Quote", "s:enquiry"), ("⬅ Supply Chain", "s:supply")]
    nav(to, phone, msg, items)
    return None

def flat(form): return [f for s in form["sections"] for f in s["fields"]]

def cust_values(cust):
    v = {k: (cust or {}).get(k, "") for k in ("name", "company", "gst", "email", "uc_code", "portal_access")}
    for k, _ in OPT.REPRESENTATIVES:
        r = ((cust or {}).get("reps") or {}).get(k, {})
        v[f"{k}_name"], v[f"{k}_mobile"] = r.get("name", ""), r.get("mobile", "")
    return v

def _c(x, n=120): return re.sub(r"\s+", " ", str(x or "")).strip()[:n]

def mobile10(x):
    d = _digits(x)
    return d[-10:] if len(d) >= 10 else ""

def validate_customer(vals, phone):
    c, errs = {k: _c(vals.get(k)) for k in customer_form_keys()}, {}
    if len(c["name"]) < 2: errs["name"] = "Please enter the customer name"
    if not c["company"]: errs["company"] = "Please enter the company / firm name"
    if c.get("email") and not EMAIL_RE.match(c["email"]): errs["email"] = "Enter a valid email address"
    c["gst"] = c["gst"].upper().replace(" ", "")
    if c["gst"] and not GST_RE.match(c["gst"]): errs["gst"] = "Invalid GST number (15 characters, e.g. 27ABCDE1234F1Z0)"
    elif c["gst"]:        # existing customer -> UC code from database | new customer -> verified on GST portal + new UC code generated
        g = gstverify.resolve(c["gst"])
        if not g["ok"]: errs["gst"] = g["error"]
        else: c["uc_code"] = g["uc_code"]        # always server-side: a typed / edited UC code is ignored
    reps, first = {}, ""
    for k, _ in OPT.REPRESENTATIVES:
        nm, raw = c[f"{k}_name"], c[f"{k}_mobile"]
        mb = mobile10(raw)
        if raw and not mb: errs[f"{k}_mobile"] = "Enter a valid 10-digit mobile number"
        if nm or mb: reps[k] = {"name": nm, "mobile": mb}
        first = first or mb
    if not first and not phone and not [e for e in errs if e.endswith("_mobile")]:
        errs[f"{OPT.REPRESENTATIVES[0][0]}_mobile"] = "Add at least one mobile number so our team can reach you"
    c["reps"] = reps; c["_first"] = first
    return c, errs

def customer_form_keys():
    return ["name", "company", "gst", "email", "uc_code", "portal_access"] + [f"{k}_{x}" for k, _ in OPT.REPRESENTATIVES for x in ("name", "mobile")]

ITEM_KEYS = ("product", "size", "thickness", "length", "qty", "grade", "standard", "brand", "delivery_date")
MAX_ITEMS = 10      # one enquiry = the main requirement + up to 9 more products ("+ Add another product" on the enquiry page)

def validate_items(items):
    """Extra product requirements of ONE enquiry -> ([clean item dicts], {index: {field: error}})."""
    out, errs = [], {}
    for i, it in enumerate((items or [])[:MAX_ITEMS - 1]):
        c, e = validate_enquiry({**(it if isinstance(it, dict) else {}), "remarks": ""})     # remarks belong to the whole enquiry
        if e: errs[i] = e
        else: out.append({k: c.get(k) or "-" for k in ITEM_KEYS})
    return out, errs

def validate_enquiry(vals):
    keys = [f["name"] for f in flat(enquiry_form())]
    c, errs = {k: _c(vals.get(k), 500 if k == "remarks" else 120) for k in keys}, {}
    if c["product"] in SUBS: errs["product"] = f"Please select the {c['product']} type"
    elif c["product"] not in PRODUCTS: errs["product"] = "Please select a product"
    for k, lab in (("size", "size"), ("thickness", "thickness / schedule"), ("length", "length"), ("qty", "quantity")):
        if not c[k]: errs[k] = f"Please enter the {lab}"
    if c["length"].lower() == "other": errs["length"] = "Please type the length"
    if c.get("brand", "").lower() == "other": errs["brand"] = "Please type the brand name"
    if c.get("unit"):
        if c["unit"] not in UNITS: errs["unit"] = "Please select the unit"
        elif c["qty"]: c["qty"] = f'{c["qty"]} {c["unit"]}'
    c["standard"], c["grade"] = OPT.split_std_grade(c.get("std_grade"))     # saved as before, so admin / PDF / Excel keep working
    if c["delivery_date"].lower().startswith("immed") or c["delivery_date"].lower() in ("asap", "urgent"): c["delivery_date"] = "Immediate"
    elif c["delivery_date"]:
        d = parse_date(c["delivery_date"])
        if not d: errs["delivery_date"] = "Invalid date"
        elif d < now_ist().date(): errs["delivery_date"] = "Date can't be in the past"
        else: c["delivery_date"] = d.strftime("%d-%m-%Y")
    return c, errs

def parse_date(t):
    t = str(t).strip().replace(" ", "")
    for fm in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d"):
        try: return datetime.strptime(t, fm).date()
        except ValueError: pass
    return None

def reps_text(reps):
    lab = dict(OPT.REPRESENTATIVES)
    return "; ".join(f"{lab[k]}: {r.get('name') or '-'} ({r.get('mobile') or '-'})" for k, r in (reps or {}).items() if k in lab)

def summary_rows(doc):
    rows = [("Company", "company"), ("Product", "product"), ("Size / NB / OD", "size"), ("Thickness / Schedule", "thickness"),
            ("Length", "length"), ("Grade", "grade"), ("Standard", "standard"), ("Brand Preference", "brand"),
            ("Quantity", "qty"), ("Delivery Date", "delivery_date"), ("Remarks", "remarks")]
    return [[a, doc.get(k) if doc.get(k) not in (None, "", "-") else "Not specified"] for a, k in rows]

def summary(doc):
    return "\n".join(f"• {a}: *{v}*" for a, v in summary_rows(doc))

# ------------------------------------------------------------------ show forms
def show_customer_form(key, to, phone, cust, prefix="", vals=None, errs=None):
    if phone is None:      # web: always the full-page "Send an Enquiry" form ("Your Details" sits at its top for new visitors)
        return show_enquiry_form(key, to, phone, cust)
    return wa_start(key, to, phone, "customer", cust, prefix)

def show_enquiry_form(key, to, phone, cust, prefix="", vals=None, errs=None):
    if phone is not None and vals: return wa_start(key, to, phone, "enquiry", cust, prefix, vals)
    if phone is None:      # web: the Enquiry Form opens as a full page (Contact Details left, form right) - see templates/home.html buildEQ()
        set_state(key, "ENQ", {"vals": vals or {}})
        return send_text(to, "", page="eq")      # no filler bubble - the client opens the form page by itself
    return wa_start(key, to, phone, "enquiry", cust, prefix)

def show_form(fid, key, to, phone, cust, prefix="", vals=None, errs=None):
    if fid == "customer": return show_customer_form(key, to, phone, cust, prefix, vals, errs)
    if fid == "enquiry": return show_enquiry_form(key, to, phone, cust, prefix, vals, errs)
    if phone is None and fid == "job":      # web: the Job Application form is a full page (templates/home.html buildJB) - nothing is added to the chat
        set_state(key, "MENU", {})
        return send_text(to, "", page="jb")
    if phone is None:
        set_state(key, "XFORM", {"fid": fid})
        return send_text(to, prefix + "Please fill the form below 👇", form=get_form(fid, vals, errs), ph="Fill the form above…")
    return wa_start(key, to, phone, fid, cust, prefix)

# ------------------------------------------------------------------ submit
def submit(key, to, phone, fid, vals, cust, items=None):
    """Validate + save.  Returns errs dict (nothing saved) or None (saved and replies sent)."""
    if fid in ("job", "vendor"): return simple_submit(key, to, phone, fid, vals)
    if fid == "customer":
        c, errs = validate_customer(vals, phone)
        if errs: return errs
        ph = phone or ("91" + c["_first"] if c["_first"] else "-")
        database().customers.update_one({"_id": key},
            {"$set": {"name": c["name"], "company": c["company"], "gst": c["gst"], "email": c.get("email", ""), "uc_code": c["uc_code"],
                      "portal_access": c["portal_access"], "reps": c["reps"], "phone": ph, "location": "-",
                      "source": "whatsapp" if phone else "web"}, "$setOnInsert": {"created": now_ist()}}, upsert=True)
        cust = database().customers.find_one({"_id": key})
        show_enquiry_form(key, to, phone, cust, prefix=f"✅ Thanks, *{c['name']}*! Your details are saved.\n\n")
        return None
    if not cust: return {"product": "Please fill the Customer Details Form first"}
    c, errs = validate_enquiry(vals)
    more, ierrs = validate_items(items)
    if ierrs: errs = {**errs, "_items": ierrs}
    if errs: return errs
    no = next_no()
    doc = {"no": no, "source": "whatsapp" if phone else "web", "status": "New", "created": now_ist(), "name": cust["name"],
           "phone": cust.get("phone", "-"), "customer_location": "-", "location": "-", "company": cust.get("company", ""),
           "gst": cust.get("gst", ""), "email": cust.get("email", ""), "uc_code": cust.get("uc_code", ""), "portal_access": cust.get("portal_access", ""),
           "reps": reps_text(cust.get("reps"))}
    for k in ("product", "size", "thickness", "length", "qty", "grade", "standard", "brand", "delivery_date", "remarks"): doc[k] = c.get(k) or "-"
    if more: doc["more_items"] = more           # 2nd, 3rd ... product of the same enquiry (the 1st stays in the normal fields, so admin / PDF / Excel keep working)
    doc["lang"] = _LANG.get()
    doc["dl_token"] = secrets.token_urlsafe(16)      # private key for the customer's PDF download link (enquiry no. alone is guessable)
    database().enquiries.insert_one(doc)
    set_state(key, "DONE", {})
    cf = confirm.start(doc)          # WhatsApp confirmation to the customer (runs in background; 'queued' = will be sent)
    wa_note = (f"\n📲 A confirmation will also be sent on WhatsApp to *{fmt_phone(norm(doc['phone']))}*." if cf == "queued" else "")
    mailer.start(doc)                # emails the enquiry PDF to every admin with an email saved (runs in background)
    if sales_quote.enabled(): sales_quote.start(doc)      # mail to the SALES person: product available / not available + a box to write the price; the price then goes to the customer automatically
    else: sheet_quote.start(doc)     # (SALES_QUOTE=0) old behaviour: emails the customer the matching price/stock straight from the Google Sheet
    n = os.getenv("NOTIFY_NUMBER")
    if n: send_text(n, f"New enquiry #{no}: {doc['name']} ({doc['company']}) {doc['phone']} – {doc['product']}, {doc['size']}, qty {doc['qty']}" + (f" (+{len(more)} more product{'s' if len(more) > 1 else ''})" if more else ""))
    if phone is None:    # web chat: no summary card / call note - the app shows the 'Thank you' popup, and the chat keeps ONLY the Contact option
        pdf_url = f"/enquiry/{no}/pdf?t={doc['dl_token']}"
        send_text(to, f"✅ *Enquiry #{no} submitted!*\nTap the button below to download your official receipt (PDF).{wa_note}",
                  thanks={"no": no, "name": doc["name"], "t": doc["dl_token"]}, links=[("📄 Download Enquiry PDF", pdf_url)],
                  chips=[("📞 Contact Us", "s:contact")], ph="Tap an option above…", lt="Select next step")
    else:
        send_text(to, f"✅ *Enquiry #{no} submitted!*\nThanks, *{doc['name']}*.\n\n📋 *Summary*\n{summary(doc)}\n\n{contact_line(doc)}\n\n_Send *enquiry* for a new enquiry • *menu* for the main menu._")
    return None

def on_form(key, to, phone, payload, state, cust):
    """Web form submitted: '@@FORM@@{"id":..., "values":{...}}'"""
    try: p = json.loads(payload[:20000]); fid, vals = p["id"], dict(p["values"])
    except Exception: return welcome(to, phone, cust)
    if fid not in ("customer", "enquiry", "job", "vendor"): return welcome(to, phone, cust)
    errs = submit(key, to, phone, fid, vals, cust)
    if errs:
        msg = "⚠️ Please correct the highlighted field(s) and submit again."
        return show_form(fid, key, to, phone, cust, prefix=msg + "\n\n", vals=vals, errs=errs)

# ------------------------------------------------------------------ WhatsApp: same forms, question by question
def wa_opts(f, vals):
    if f.get("options"): return f["options"]
    if f.get("lists"):
        L = f["lists"]; return L.get(vals.get(f.get("depends", ""))) or L["default"]
    return []

def wa_start(key, to, phone, fid, cust, prefix="", vals0=None):
    form = get_form(fid, cust_values(cust) if fid == "customer" else (vals0 or {}))
    vals = {f["name"]: f["val"] for f in flat(form)}
    set_state(key, "WAFORM", {"fid": fid, "i": 0, "vals": vals})
    return wa_ask(to, form, 0, vals, prefix)

def wa_ask(to, form, i, vals, prefix="", err=""):
    form = i18n.form_tr(form, _LANG.get())          # Hindi labels / placeholders when the customer chose Hindi
    fl = flat(form); f = fl[i]; opts = wa_opts(f, vals)
    q = f"{prefix}{err}*{form['title']}*  ({i + 1}/{len(fl)})\n\n*{f['label']}*" + (" *(required)*" if f["req"] else " _(optional)_")
    if f["type"] == "date": q += "\n_Type a date as DD-MM-YYYY_" + ("  _or reply *immediate*_" if f.get("immediate") else "")
    if opts: q += "\n" + "\n".join([f"{n}. {o}" for n, o in enumerate(opts, 1)]) + ("\n_Reply with a number" + (" or type your own_" if f.get("lists") or f.get("other") else "_") )
    elif f.get("ph"): q += f"\n_{f['ph']}_"
    cur = vals.get(f["name"])
    if cur: q += f"\n_Saved: {cur} – send *ok* to keep it_"
    if not f["req"]: q += "\n_*skip* to leave blank_"
    return send_text(to, q)

def sub_menu(parent, items):
    return f"*{parent}* – select type\n" + "\n".join(f"{n}. {o}" for n, o in enumerate(items, 1)) + "\n_Reply with a number_"

def wa_input(key, to, phone, t, data, cust):
    fid, i, vals = data["fid"], data["i"], data["vals"]
    form = get_form(fid, vals)
    fl = flat(form); f = fl[i]; low = t.lower(); opts = wa_opts(f, vals)
    sub = data.get("sub"); so = (f.get("subs") or {}).get(sub or "")
    if so:                                                       # WhatsApp: the 3 sub-options of the chosen heading are open
        names = [x.lower() for x in so]
        if t.isdigit() and 1 <= int(t) <= len(so): val = so[int(t) - 1]
        elif low in names: val = so[names.index(low)]
        else: return send_text(to, "⚠️ Please reply with a number from the list.\n\n" + sub_menu(sub, so))
        data.pop("sub", None)
    elif low == "skip" and not f["req"]: val = ""
    elif low == "ok" and vals.get(f["name"]): val = vals[f["name"]]
    elif f.get("other") and (low == "other" or (t.isdigit() and 1 <= int(t) <= len(opts) and opts[int(t) - 1] == "Other")):
        return send_text(to, f"✍️ {f['other']}")          # "Other" picked -> the customer types the value in the next message
    elif opts and t.isdigit() and 1 <= int(t) <= len(opts): val = opts[int(t) - 1]
    elif f.get("options") and f["type"] == "select" and not f.get("other"): return wa_ask(to, form, i, vals, err="⚠️ Please reply with a number from the list.\n\n")
    else: val = t
    if f.get("subs") and val in f["subs"]:                       # e.g. "MS ERW Pipe" picked -> open its sub-options
        data["sub"] = val; set_state(key, "WAFORM", data)
        return send_text(to, sub_menu(val, f["subs"][val]))
    vals[f["name"]] = val
    if i + 1 < len(fl):
        data["i"] = i + 1; set_state(key, "WAFORM", data)
        return wa_ask(to, form, i + 1, vals)
    errs = submit(key, to, phone, fid, vals, cust)
    if not errs: return
    j = next(n for n, x in enumerate(fl) if x["name"] in errs)       # ask the first wrong field again
    data["i"] = j; set_state(key, "WAFORM", data)
    return wa_ask(to, form, j, vals, err=f"⚠️ {errs[fl[j]['name']]}\n\n")

# ------------------------------------------------------------------ NEW FLOW: navigation (web = tap chips, WhatsApp = numbered list)
def nav(to, phone, text, items, home=True, imgs=None, card=None, image=None, lt="Select next step", extra=None, popup=None):
    """Send `text` (+ images / table) followed by tappable options.  items = [(label, token)].  Numbers 1..n pick items on WhatsApp."""
    items = list(items) + ([HOME] if home else [])
    set_state(KEY.get(), "NAV", {"menu": [t for _, t in items]})
    if phone is None:
        kw = {}
        if imgs: kw["gallery"] = [{"img": u, "cap": c} for u, c in imgs]; kw["poster"] = imgs[0][0]
        if card: kw["card"] = card
        if image: kw["image"] = image
        if extra: kw["extra"] = extra          # web chat: more one-tap buttons shown under the "Select ..." button
        if popup: kw["popup"] = popup          # web chat: no chat bubble - the app opens the options as a popup instead
        return send_text(to, text, chips=items, ph="Tap an option above…", lt=lt, **kw)
    b = base_url(phone)
    for u, c in (imgs or [])[:4]: send_image(to, b + u, c)
    if card: text += "\n\n" + "\n".join(f"- {a}: *{v}*" for a, v in card["rows"])
    return send_text(to, text + "\n\n" + "\n".join(f"{n}. {l}" for n, (l, _) in enumerate(items, 1)) + "\n\n_Reply with a number • 0 = main menu_")

def quiet(items):
    """Web chat: the page / popup opens by itself, so no filler bubble ('... opened. Tap below to continue') is sent - only the navigation state is kept."""
    set_state(KEY.get(), "NAV", {"menu": [t for _, t in items]})

TOUR = ["about", "products", "resource", "supply", "services", "enquiry", "contact"]       # "jobs" (Join our Team) now lives ONLY in the Select user type popup
SECTIONS = {"about": "ℹ️ About Us", "products": "📦 Products", "resource": "📚 Resource", "supply": "🚚 Supply Chain", "services": "🛠 Services",
            "jobs": "💼 Join our Team", "enquiry": "📋 Product Enquiry Form", "contact": "📞 Contact Us"}
ABOUT_BTNS = {"history": ("📜 Our History", None), "vision": ("🎯 Vision, Mission & Values", None), "mgmt": ("👥 Management", None)}
def about_sub(v):          # WhatsApp About Us texts - read live from the official website (falls back to options.py)
    try:
        d = about_fetch.get_about(); return {"history": about_fetch.wa_history, "vision": about_fetch.wa_vision, "mgmt": about_fetch.wa_mgmt}[v](d)
    except Exception:
        return {"history": OPT.ABOUT_HISTORY, "vision": OPT.ABOUT_VISION, "mgmt": OPT.ABOUT_MGMT}[v]
def about_main():
    try: return about_fetch.wa_main(about_fetch.get_about())
    except Exception: return OPT.ABOUT_TEXT
ABOUT_SUB = {"history": None, "vision": None, "mgmt": None}
def prod_btns(phone): return [] if phone is None else [(OPT.PRODUCT_INFO[x][0], "p:" + x) for x in ("gi", "ms", "hollow", "seamless", "gp")]
def nxt(k): return [(f"Next ➡ {SECTIONS[TOUR[TOUR.index(k) + 1]][2:]}", "s:" + TOUR[TOUR.index(k) + 1])] if k != "contact" else []

def open_enquiry(key, to, phone, cust, product=None):
    vals = {"product": product} if product else None
    # web: the Enquiry Form page opens the same way on EVERY device (new visitors fill "Your Details" at the top of that page);
    # WhatsApp keeps the Customer Details step because the number is only known there
    if cust or phone is None: return show_enquiry_form(key, to, phone, cust, vals=vals)
    return show_customer_form(key, to, phone, cust, prefix="Please share your details first 👇\n\n")

def route(key, to, phone, cust, tk):
    """Resolve a navigation token ('s:about', 'p:gi', 'r:cat' ...) - returns True if handled."""
    k, _, v = tk.partition(":")
    if tk == "u:home":      # after the customer has visited Home -> ask Existing / New user
        nav(to, phone, "*Are you an existing user?*", USER_ITEMS, home=False, lt="Select user type"); return True
    if tk == "u:exist": set_utype(key, "exist"); open_enquiry(key, to, phone, cust); return True
    if tk == "u:new":       # New User -> full menu of sections (nothing opens by itself; customer picks / types)
        set_utype(key, "new")
        items = [("🏠 Home", "u:home"), ("ℹ️ About Us", "s:about"), ("📦 Products", "s:products"), ("📚 Resources", "s:resource"),
                 ("🚚 Supply Chain", "s:supply"), ("🛠 Services", "s:services")]
        nav(to, phone, "Welcome to *Shreeji SteelTubes Pvt. Ltd.* 🙏\nPlease choose what you would like to see 👇", items, home=False, lt="Select section",
            popup="sections"); return True
    if k == "a" and v in ABOUT_SUB:
        text = about_sub(v)
        back = [(l, "a:" + x) for x, (l, _) in ABOUT_BTNS.items() if x != v]
        nav(to, phone, text, back + [("⬅ About Us", "s:about")] + nxt("about"), lt="Select About Us topic"); return True
    if tk == "s:all": nav(to, phone, "*All sections* 👇", [(l, "s:" + x) for x, l in SECTIONS.items() if x != "jobs"], lt="Select section"); return True
    if k == "s" and v in SECTIONS:
        if v == "about":
            if phone is None:   # web chat: the About Us page (like Home) opens full screen; chat only gets a short note
                # web chat: About Us opens full screen by itself; chat gets ONE button -> Products
                quiet([("📦 Products", "s:products")])
            else:
                nav(to, phone, about_main(), [(l, "a:" + x) for x, (l, _) in ABOUT_BTNS.items()] + nxt(v), imgs=OPT.ABOUT_IMAGES, lt="Select About Us topic")
        elif v == "products":
            if phone is None: quiet(prod_btns(phone) + nxt(v))
            else: nav(to, phone, "*Our Products*\nChoose a product 👇", prod_btns(phone) + nxt(v), lt="Select product")
        elif v == "resource":
            nav(to, phone, "*Resource*\nChoose one 👇", [("📘 Product Catalogue", "r:cat"), ("🏅 Certificates", "r:cert"), ("✅ Quality Assurance", "r:qa"), ("🖼 Gallery", "r:gal"), ("📄 Documents", "r:dl")] + nxt(v), lt="Select resource")
        elif v == "supply":
            sc = [("🏭 Authorised Dealers & Distributors", "v:dealers"), ("💬 Request For Quote", "v:rfq"), ("🤝 Vendor Registration", "v:vendor"), ("👥 Clients", "v:clients")]
            if phone is None:   # web chat: the app opens the Supply Chain selection popup (like Resources) - no chat bubble
                set_state(KEY.get(), "NAV", {"menu": [t for _, t in sc + [HOME]]})
                send_text(to, "🚚 Supply Chain", popup="supply")
            else:
                nav(to, phone, "*Supply Chain*\nChoose one 👇", sc + nxt(v), lt="Select supply chain topic")
        elif v == "services":
            if phone is None:   # web chat: the Services page opens full screen - chat gets only a short note + Next button (no long text / photo)
                quiet(nxt(v))
            else:
                nav(to, phone, OPT.SERVICES_TEXT, nxt(v), imgs=[(OPT.H + "services.jpg", "Our Services")])
        elif v == "jobs": show_form("job", key, to, phone, cust)
        elif v == "enquiry": open_enquiry(key, to, phone, cust)
        elif phone is None:   # web chat: the Contact page (details + message form + office & stock-yard maps) opens full screen - chat gets only a short note
            quiet([("⬅ All sections", "s:all"), ("📋 Product Enquiry Form", "s:enquiry")])
        else:
            rows = contact_rows()
            if phone: send_text(to, "*Contact Details (Department wise)*\n" + "".join(f"\n*{r['department']}*\n" + (r['name'] + "\n" if r['name'] else "") + (f"📞 {r['phone']}\n" if r['phone'] else "") + (f"✉️ {r['email']}\n" if r['email'] else "") for r in rows))
            else: send_text(to, "*Contact Details (Department wise)*", contacts=rows)
            visit_card(to, phone)
            nav(to, phone, "👆 Tap below to continue", [("⬅ All sections", "s:all"), ("📋 Product Enquiry Form", "s:enquiry")])
        return True
    if k == "p" and phone is None and v in ("gi", "ms", "hollow", "seamless", "gp"):   # web: the product page opens full screen; chat shows the 5 product buttons again
        quiet(prod_btns(phone) + nxt("products")); return True
    if k == "p" and v in OPT.PRODUCT_INFO:
        lab, img, title, rows, desc, prod = OPT.PRODUCT_INFO[v]
        items = [("📋 Enquire this product", "q:" + v)]
        if v == "ms": items = [("MS Black Pipe", "p:msblack"), ("Large Diameter Pipe", "p:ldp")] + items
        nav(to, phone, f"*{lab}*\n{desc}", items + [("⬅ Products", "s:products")] + nxt("products"), imgs=[(OPT.H + img, lab)], card={"title": title, "rows": rows}); return True
    if k == "q" and v in OPT.PRODUCT_INFO: open_enquiry(key, to, phone, cust, OPT.PRODUCT_INFO[v][5]); return True
    if k == "r":
        back = [("⬅ Resource", "s:resource")] + nxt("resource")
        if v == "qa": nav(to, phone, OPT.QA_TEXT, back, imgs=[(OPT.H + "awards.jpg", "Quality & Certifications")])
        elif v == "gal":
            for u, fn, t_ in catalog_docs("awards"): send_document(to, base_url(phone) + u, fn, t_)
            nav(to, phone, "*Gallery*" + ("\n_Swipe to see more_" if phone is None else ""), back, imgs=OPT.GALLERY_IMAGES)
        elif v in ("cat", "cert"):
            docs = catalog_docs("catalogue" if v == "cat" else "certificate")
            for u, fn, t_ in docs: send_document(to, base_url(phone) + u, fn, t_)
            if phone is None and docs: quiet(back)
            else: nav(to, phone, ("✅ Sent! 👆" if docs else "ℹ️ This will be shared soon."), back)
        elif v == "dl":
            docs = catalog_docs("datasheet") + catalog_docs("documents")
            if not docs: nav(to, phone, "ℹ️ No documents added yet. Our team will add them soon.", back)
            else: nav(to, phone, "*Documents*\nTap a document to receive it 👇", [(t_, f"d:{n}") for n, (_, _, t_) in enumerate(docs)] + back, lt="Select document")
        return True
    if k == "d" and v.isdigit():
        docs = catalog_docs("datasheet") + catalog_docs("documents")
        if int(v) < len(docs): u, fn, t_ = docs[int(v)]; send_document(to, base_url(phone) + u, fn, t_)
        return route(key, to, phone, cust, "r:dl")
    if k == "v":
        back = [("⬅ Supply Chain", "s:supply")] + nxt("supply")
        if v == "dealers":
            if phone is None: quiet(back)   # web chat: full-screen page (like About Us)
            else: nav(to, phone, OPT.DEALERS_TEXT, back, imgs=[(OPT.H + "ldp.jpg", "Authorised distributor of leading brands")])
        elif v == "clients": nav(to, phone, OPT.CLIENTS_TEXT, back, imgs=[(OPT.H + "industries.jpg", "Industries we serve")])
        elif v == "rfq":
            if phone is None: quiet(back)   # web chat: full-screen page (like About Us)
            else: open_enquiry(key, to, phone, cust)
        elif v == "vendor":
            if phone is None: quiet(back)   # web chat: full-screen page (like Request For Quote)
            else:             # WhatsApp: the full Vendor Registration Form (PAN, GST, bank details, documents...) is too long for chat - send the link
                b = base_url(phone)
                nav(to, phone, "🤝 *Vendor Registration*\nPlease fill our Vendor Registration Form here 👇\n" + (b + "/vendor-registration" if b else "(our website)") +
                    "\n\n_Keep your PAN, GST and bank details ready. You can also attach your documents in the form._", back)
        return True
    return False

# ------------------------------------------------------------------ language switch + voice
def get_cust(key): return database().customers.find_one({"_id": key})

def change_language(key, to, phone, cust, state, data, lc):
    """'hindi' / 'english' / header button ('toggle') / 'language' (ask).  Re-shows the current screen in the new language."""
    cur = get_lang(key)
    if lc == "toggle": lc = "en" if cur == "hi" else "hi"
    if lc == "ask":
        if phone is None: return send_text(to, i18n.ASK, chips=[("🇮🇳 हिंदी", "lang:hi"), ("🇬🇧 English", "lang:en")], lt="Language / भाषा")
        return send_text(to, i18n.ASK + "\n\nReply *hindi* ya *english*")
    set_lang(key, lc); _LANG.set(lc)
    send_text(to, i18n.SWITCHED[lc])
    if state == "CFORM": return show_customer_form(key, to, phone, cust)
    if state == "ENQ": return show_enquiry_form(key, to, phone, cust)
    if state == "XFORM": return show_form((data or {}).get("fid", "job"), key, to, phone, cust)
    if state == "WAFORM" and data:
        return wa_ask(to, get_form(data["fid"], data["vals"]), data["i"], data["vals"])
    set_state(key, "MENU", {}); return welcome(to, phone, cust)

def handle_voice(key, text, phone):
    """WhatsApp voice note -> text (already transcribed).  text=None means transcription was not possible."""
    KEY.set(key); _LANG.set(get_lang(key))
    if not text:
        return send_text(phone, "🎤 Sorry, I could not understand your voice message. Please type your message or send *hi*.")
    send_text(phone, f"🎤 You said: _{text[:300]}_")
    return handle(key, text, phone=phone)

# ------------------------------------------------------------------ main entry
# ------------------------------------------------------------------ Free-text understanding (English + Hinglish)
# Customers do not always tap buttons - they type "price of GI pipe", "catalogue bhejo", "address kya hai" ...
# Each rule: (regex on the lower-case message, navigation token / special word). First match wins, specific before general.
INTENTS = [
    (r"^(hi+|hello+|hey+|hii+|namaste|namaskar|good (morning|afternoon|evening))\b", "greet"),
    (r"\b(thanks?|thank you|thx|shukriya|dhanyavad|dhanyawad)\b", "thanks"),
    (r"\b(bye|goodbye|tata|alvida)\b", "bye"),
    (r"\b(help|madad|options?|what can you do|kya kar sakte)\b", "help"),
    (r"\b(gi|galvani[sz]ed)\b", "p:gi"),
    (r"\b(pre.?galvani[sz]ed|gp)\b", "p:gp"),
    (r"\b(large diameter|ldp|spiral|h-?saw|l-?saw)\b", "p:ldp"),
    (r"\b(shs|rhs|chs|hollow|square|rectangular|structural)\b", "p:hollow"),
    (r"\b(seamless)\b", "p:seamless"),
    (r"\b(ms|mild steel|black pipe|erw)\b", "p:ms"),
    (r"\b(catalogue|catalog|catalouge|brochure|datasheet|data sheet|weight chart|weight|sizes?|thickness|dimensions?|specifications?|specs?|chart|pdf)\b", "r:cat"),
    (r"\b(certificates?|certification|iso|dealership)\b", "r:cert"),
    (r"\b(documents?|pan card|pan|udyam|msme|bank details?)\b", "r:dl"),
    (r"\b(gallery|photos?|images?|pictures?)\b", "r:gal"),
    (r"\b(quality|testing)\b", "r:qa"),
    (r"^(existing( customer| user)?|old customer|regular customer|purana( customer| user)?)$", "u:exist"),
    (r"^(new( user| customer)?|naya( customer| user)?)$", "u:new"),
    (r"\b(about|overview|history|vision|mission|values|management|profile|introduction|who are you|company|shreeji|srj)\b", "s:about"),
    (r"\b(resources?|downloads?|videos?|awards?|achievements?)\b", "s:resource"),
    (r"\b(godown|stock|stockyard|warehouse|yard|office|branch|branches|timings?|whatsapp)\b", "s:contact"),
    (r"\b(apply|application|resume|cv|hr|vacancies)\b", "s:jobs"),
    (r"\b(gst|gstin|uc code)\b", "enquiry"),
    (r"\b(cutting|bending|grinding|polishing|coating|processing|fabrication)\b", "s:services"),
    (r"\b(price|prices|rate|rates|quote|quotation|rfq|bhav|bhaav|kimat|daam|cost|enquiry|inquiry|order|buy|kharid\w*|chahiye|require\w*)\b", "enquiry"),
    (r"\b(contact|call|phone|number|mobile|email|mail|address|location|map|visit|sampark|pata)\b", "s:contact"),
    (r"\b(jobs?|career|careers|vacancy|hiring|naukri)\b", "s:jobs"),
    (r"\b(dealers?|distributors?|clients?|vendor|supply)\b", "s:supply"),
    (r"\b(services?)\b", "s:services"),
    (r"\b(products?|pipes?|tubes?|steel|sections?|rectangle|round|galvani[sz]ing|zinc|hot dip)\b", "s:products"),
]
INTENTS = [(re.compile(p), t) for p, t in INTENTS]

# Hindi (Devanagari) words - typed in Hindi or spoken through voice input.  No \b here: Devanagari vowel signs are not "word" characters.
INTENTS_HI = [
    (r"^(नमस्ते|नमस्कार|हेलो|हैलो|हाय|प्रणाम)", "greet"),
    (r"(धन्यवाद|शुक्रिया|थैंक)", "thanks"),
    (r"(अलविदा|टाटा|बाय)", "bye"),
    (r"(मदद|सहायता|हेल्प|विकल्प)", "help"),
    (r"(प्री.?गैल्वनाइज्ड|जीपी)", "p:gp"),
    (r"(जीआई|गैल्वनाइज्ड|गैलवनाइज्ड)", "p:gi"),
    (r"(लार्ज डायमीटर|स्पाइरल|एलडीपी)", "p:ldp"),
    (r"(हॉलो|होलो|चौकोर|आयताकार|स्क्वायर|रेक्टेंगुलर|स्ट्रक्चरल)", "p:hollow"),
    (r"(सीमलेस|सीमलैस)", "p:seamless"),
    (r"(एमएस|माइल्ड स्टील|ब्लैक पाइप|ईआरडब्ल्यू)", "p:ms"),
    (r"(कैटलॉग|कैटलोग|ब्रोशर|डेटाशीट|वेट चार्ट)", "r:cat"),
    (r"(प्रमाणपत्र|प्रमाण पत्र|सर्टिफिकेट|आईएसओ)", "r:cert"),
    (r"(दस्तावेज|डॉक्यूमेंट|डाक्यूमेंट|पैन कार्ड|उद्यम|बैंक डिटेल)", "r:dl"),
    (r"(गैलरी|फोटो|तस्वीर)", "r:gal"),
    (r"(गुणवत्ता|क्वालिटी|टेस्टिंग)", "r:qa"),
    (r"(भाव|कीमत|दाम|रेट|कोटेशन|पूछताछ|इंक्वायरी|एनक्वायरी|ऑर्डर|आर्डर|खरीद|चाहिए|चाहिये|जरूरत|ज़रूरत)", "enquiry"),
    (r"(संपर्क|सम्पर्क|कॉल|फोन|फ़ोन|नंबर|मोबाइल|ईमेल|पता|पते|लोकेशन|नक्शा|मैप)", "s:contact"),
    (r"(नौकरी|करियर|भर्ती|वैकेंसी|जॉब)", "s:jobs"),
    (r"(डीलर|वितरक|क्लाइंट|वेंडर|सप्लाई)", "s:supply"),
    (r"(सेवा|सर्विस)", "s:services"),
    (r"(हमारे बारे|कंपनी के बारे|कंपनी की जानकारी|कंपनी)", "s:about"),
    (r"(उत्पाद|प्रोडक्ट|पाइप|ट्यूब|स्टील)", "s:products"),
]
INTENTS_HI = [(re.compile(p), t) for p, t in INTENTS_HI]

def detect_intent(low):
    """Return a navigation token ('s:products', 'p:gi', 'enquiry' ...), 'thanks' / 'bye' / 'help', or None."""
    w = re.sub(r"[^\w\s\u0900-\u097F-]", " ", low or "")
    if re.search(r"[\u0900-\u097F]", w):
        w2 = w.replace("\u093C", "")          # ignore nukta so क़/ज़/फ़ typed either way still match
        for rx, tok in INTENTS_HI:
            if rx.search(w2): return tok
    fixed = _fix_typos(w)                   # 'prodcuts', 'catlogue', 'conact', 'seamles' ... -> corrected words first, then the same rules
    for text in ((fixed, w) if fixed != w else (w,)):
        for rx, tok in INTENTS:
            if rx.search(text): return tok
    return None

import difflib
_VOCAB = ("products product pipes pipe tubes tube steel seamless galvanized galvanised hollow square rectangular structural catalogue catalog brochure "
          "datasheet certificate certificates dealership documents document gallery photos images quality testing price prices rate quotation quote enquiry "
          "inquiry order contact address location phone mobile email jobs career careers vacancy dealers distributors clients vendor supply services service "
          "about company overview history vision mission management resources resource existing customer user new help menu home welcome thanks").split()
def _fix_typos(w):
    out = []
    for x in w.split():
        if len(x) >= 4 and x not in _VOCAB:
            m = difflib.get_close_matches(x, _VOCAB, n=1, cutoff=0.78)
            x = m[0] if m else x
        out.append(x)
    return " ".join(out)

HELP_TEXT = ("\U0001F4A1 *How can I help you?*\nYou can tap the buttons, or simply type:\n"
             "\u2022 *products* \u2013 our pipes & tubes (GI, MS, Hollow Sections, Seamless, GP)\n"
             "\u2022 *price* / *enquiry* \u2013 send your requirement\n"
             "\u2022 *catalogue* / *documents* / *certificates* \u2013 get files\n"
             "\u2022 *contact* \u2013 call, email & address\n"
             "\u2022 *menu* \u2013 back to the main menu")
UNKNOWN_TEXT = ("\U0001F64F Sorry, I could not find that.\nPlease pick an option below, or type *products*, *price*, *catalogue*, *contact* or *help* \U0001F447")

def handle(key, text, phone=None):
    """key = 'web:<session>' or 'wa:<phone>'.  phone = known number (WhatsApp only)."""
    to = phone or key; KEY.set(key); _LANG.set(get_lang(key))
    raw = (text or "").strip()
    state, data = get_state(key)
    lc = None if raw.startswith(FORM_TAG) else i18n.lang_command(raw)
    if lc and (state != "WAFORM" or lc in ("hi", "en")):      # 'hindi' / 'english' / 'language' typed or tapped
        return change_language(key, to, phone, get_cust(key), state, data, lc)
    cust = database().customers.find_one({"_id": key})
    if raw.startswith(FORM_TAG): return on_form(key, to, phone, raw[len(FORM_TAG):], state, cust)
    t = raw[:500]; low = t.lower()
    if state != "WAFORM":     # typed words open the same page as the tab/button: "about us" -> About Us page, "home" -> Home page
        w = re.sub(r"[^\w\s-]", "", low).strip()
        if ABOUT_RE.search(w): t = "s:about"
        elif w == "home": t = "u:home"

    if low in ("hi", "hello", "hey", "menu", "0", "start", "मेन्यू", "शुरू"):
        set_state(key, "MENU", {}); return welcome(to, phone, cust, greet=low in GREET)
    if low == "enquiry": return open_enquiry(key, to, phone, cust)
    if state == "NAV" and t.isdigit() and 1 <= int(t) <= len((data or {}).get("menu", [])): t = data["menu"][int(t) - 1]
    if ":" in t and route(key, to, phone, cust, t): return
    if state == "CFORM": return show_customer_form(key, to, phone, cust, prefix="👆 ")
    if state == "ENQ":   return show_enquiry_form(key, to, phone, cust, prefix="👆 ")
    if state == "XFORM": return show_form(data.get("fid", "job"), key, to, phone, cust, prefix="👆 ")
    if state == "WAFORM": return wa_input(key, to, phone, t, data, cust)
    it = detect_intent(low)
    if it == "greet": set_state(key, "MENU", {}); return welcome(to, phone, cust, greet=True)
    if it == "thanks": send_text(to, "\U0001F60A You are welcome! Anything else I can help you with?"); return welcome(to, phone, cust)
    if it == "bye": return send_text(to, "\U0001F64F Thank you for visiting *Shreeji SteelTubes Pvt. Ltd.*. Have a great day! Send *hi* anytime to chat again.")
    if it == "help": send_text(to, HELP_TEXT); return welcome(to, phone, cust)
    if it == "enquiry": return open_enquiry(key, to, phone, cust)
    if it and route(key, to, phone, cust, it): return
    if t: send_text(to, UNKNOWN_TEXT)
    return welcome(to, phone, cust)
