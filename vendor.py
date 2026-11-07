"""Vendor Registration - the full online version of the company's paper 'Vendor Registration Form'.

Sections (same as the PDF):  1 Company Information | 2 Statutory Details | 3 Bank Details |
                             4 Business Details | 5 Documents Enclosed | 6 Declaration
'Vendor Code' and 'For Office Use Only' (Verified by / Approved by / Date) are filled by the admin, not the vendor.

Saved in MongoDB collection `vendors`.  Uploaded documents are kept in the PRIVATE folder  vendor_docs/<no>/
(never served publicly - only an admin, or the vendor with the private download key, can open them).
"""
import os, re, shutil
from datetime import datetime
from werkzeug.utils import secure_filename

HERE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(HERE, "vendor_docs")

STATES = ["Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
          "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir",
          "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
          "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
          "Uttarakhand", "West Bengal"]
CONSTITUTIONS = ["Proprietorship", "Partnership", "LLP", "Private Limited", "Public Limited", "HUF", "Trust / Society", "Other"]
VENDOR_TYPES = ["Manufacturer", "Trader", "Service Provider", "Contractor", "Other"]
ACC_TYPES = ["Current", "Savings", "Cash Credit", "Overdraft"]
COUNTRIES = ["India", "Bangladesh", "Bhutan", "China", "Germany", "Indonesia", "Japan", "Nepal", "Singapore", "South Korea", "Sri Lanka",
             "United Arab Emirates", "United Kingdom", "United States", "Other"]
COMPANY_STATUS = ["Micro Enterprise", "Small Enterprise", "Medium Enterprise", "Large Enterprise"]      # MSME classification
STATUSES = ["New", "Verified", "Approved", "Rejected"]

# 'Documents enclosed' - tick-boxes in the PDF; online they are optional uploads (a ticked box = file received)
DOCS = [("pan_doc", "PAN Card copy"), ("gst_doc", "GST Certificate"), ("cheque_doc", "Cancelled Cheque / Bank Passbook"),
        ("msme_doc", "MSME / Udyam Certificate"), ("addr_doc", "Address Proof"), ("reg_doc", "Company Registration / Partnership Deed")]
SIGN = ("signature", "Signature & Company Seal")
FILE_KEYS = [k for k, _ in DOCS] + [SIGN[0]]
FILE_LABEL = dict(DOCS + [SIGN])

MAX_FILE = 3 * 1024 * 1024                       # 3 MB per document (7 files x 3 MB stays below the app-wide 25 MB request limit)
EXT = {".pdf": b"%PDF", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG"}      # allowed type -> real file signature

def F(name, label, type="text", req=False, ph="", options=None, full=False, **kw):
    d = dict(name=name, label=label, type=type, req=req, ph=ph, full=full); d.update(kw)
    if options: d["options"] = options
    return d

def form():
    """Form definition (sent to the web page, which draws it - one single source for labels, order and 'required')."""
    return {"title": "Vendor Registration Form", "note": "Please fill in all fields. Fields marked * are mandatory.", "notice": "GST No. and PAN No. is Mandatory in India.", "sections": [
        {"title": "1. Company Information", "fields": [
            F("firm", "Name of Firm / Company", req=True, ph="As per PAN / GST", maxlen=120),
            F("constitution", "Type of the Firm", "select", True, options=CONSTITUTIONS),
            F("country", "Country", "select", True, options=COUNTRIES, default="India"),
            F("cstatus", "Status of Company", "select", True, options=COMPANY_STATUS),
            F("vtype", "Type of Vendor", "select", options=VENDOR_TYPES),
            F("contact", "Contact Person", req=True, maxlen=80), F("designation", "Designation", maxlen=60),
            F("address", "Registered Address", "textarea", True, full=True, maxlen=300),
            F("city", "City", req=True, maxlen=60), F("state", "State", "select", True, options=STATES, india=True),
            F("pin", "PIN Code", "tel", True, ph="6 digits", maxlen=6, india=True),
            F("mobile", "Mobile No.", "tel", True, ph="10-digit mobile", maxlen=18), F("landline", "Landline", "tel", ph="With STD code", maxlen=20),
            F("email", "Email", "email", True, maxlen=120),
            F("website", "Website", ph="www.example.com", maxlen=120), F("year", "Year of Establishment", "tel", ph="e.g. 2005", maxlen=4)]},
        {"title": "2. Statutory Details", "fields": [
            F("pan", "PAN No.", req=True, ph="e.g. ABCDE1234F", upper=True, maxlen=10, india=True),
            F("gst", "GST No.", req=True, ph="e.g. 27ABCDE1234F1Z5", upper=True, maxlen=15, india=True),
            F("udyam", "MSME / Udyam Reg. No.", ph="e.g. UDYAM-MH-01-0000000", upper=True, maxlen=25),
            F("cin", "CIN / Registration No.", upper=True, maxlen=30)]},
        {"title": "3. Bank Details", "fields": [
            F("acc_name", "Account Holder Name", req=True, maxlen=100), F("bank", "Bank Name", req=True, maxlen=80),
            F("acc_no", "Account No.", "tel", True, maxlen=18), F("ifsc", "IFSC Code / SWIFT", req=True, ph="e.g. HDFC0001234", upper=True, maxlen=11, india=True),
            F("acc_type", "Account Type", "select", options=ACC_TYPES),
            F("branch", "Branch Name & Address", "textarea", full=True, maxlen=250)]},
        {"title": "4. Business Details", "fields": [
            F("products", "Products / Services Offered", "textarea", True, full=True, ph="e.g. MS pipes, transport, coating", maxlen=500),
            F("clients", "Major Clients / References", "textarea", full=True, maxlen=500),
            F("turnover", "Annual Turnover (last FY)", ph="e.g. Rs. 2.5 Crore", maxlen=60),
            F("pay_terms", "Payment Terms Offered", ph="e.g. 30 days from invoice", maxlen=80)]},
        {"title": "5. Documents Enclosed", "hint": "Attach clear copies (PDF / JPG / PNG, up to 3 MB each). You may also send them later to our team.",
         "fields": [F(k, lb, "file", full=False) for k, lb in DOCS]},
        {"title": "6. Declaration", "fields": [
            F("agree", "", "check", True, full=True,
              text="I/We hereby declare that the information furnished above is true and correct to the best of my/our knowledge. "
                   "I/We agree to inform of any changes and accept the terms and conditions of the company."),
            F("signatory", "Authorised Signatory Name", req=True, maxlen=80), F("sig_desig", "Designation", req=True, maxlen=60),
            F("place", "Place", maxlen=60), F(SIGN[0], SIGN[1], "file")]}]}

def fields():
    return [f for s in form()["sections"] for f in s["fields"]]

# ------------------------------------------------------------------ validation
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GST_RE = re.compile(r"^(0[1-9]|[1-2][0-9]|3[0-8])[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
SITE_RE = re.compile(r"^(https?://)?([A-Za-z0-9-]+\.)+[A-Za-z]{2,}(/\S*)?$")

def _t(x, n, multi=False):
    s = str(x or "").replace("\r", "")
    s = "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in s.split("\n")) if multi else re.sub(r"\s+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()[:n]

def mobile10(x):
    d = re.sub(r"\D", "", str(x or ""))
    if len(d) == 12 and d.startswith("91"): d = d[2:]
    elif len(d) == 11 and d.startswith("0"): d = d[1:]
    return d if re.fullmatch(r"[6-9]\d{9}", d) else ""

def clean(raw):
    """Validate the text fields.  Returns (values, errors) - nothing is saved here."""
    v, errs = {}, {}
    india = _t(raw.get("country"), 40) in ("", "India")
    for f in fields():
        if f["type"] == "file": continue
        n = f["name"]
        if f["type"] == "check": v[n] = str(raw.get(n, "")).strip().lower() in ("1", "true", "on", "yes"); continue
        s = _t(raw.get(n), f.get("maxlen", 120), f["type"] == "textarea")
        if f.get("upper"): s = s.upper().replace(" ", "")
        if f["type"] == "select" and s and s not in f["options"]: s = ""
        if n == "country" and not s: s = "India" if not str(raw.get("country") or "").strip() else ""
        v[n] = s
        if f["req"] and not s and (india or not f.get("india")): errs[n] = "This field is required"
    if india and v["pan"] and not PAN_RE.match(v["pan"]): errs["pan"] = "Enter a valid 10-character PAN (e.g. ABCDE1234F)"
    if india and v["gst"] and not GST_RE.match(v["gst"]): errs["gst"] = "Enter a valid 15-character GST number (e.g. 27ABCDE1234F1Z5)"
    elif india and v["gst"] and PAN_RE.match(v["pan"]) and v["gst"][2:12] != v["pan"]: errs["gst"] = "GST number does not match the PAN entered"
    if v["mobile"]:
        m = mobile10(v["mobile"]) if india else (re.sub(r"[^\d+]", "", v["mobile"]) if 7 <= len(re.sub(r"\D", "", v["mobile"])) <= 15 else "")
        if m: v["mobile"] = m
        else: errs["mobile"] = "Enter a valid 10-digit mobile number" if india else "Enter a valid mobile number with country code"
    if v["email"] and not EMAIL_RE.match(v["email"]): errs["email"] = "Enter a valid email address"
    if india and v["pin"] and not re.fullmatch(r"[1-9]\d{5}", v["pin"]): errs["pin"] = "Enter a valid 6-digit PIN code"
    if v["landline"] and not 6 <= len(re.sub(r"\D", "", v["landline"])) <= 13: errs["landline"] = "Enter a valid landline number (with STD code)"
    if v["website"] and not SITE_RE.match(v["website"]): errs["website"] = "Enter a valid website (e.g. www.example.com)"
    if v["year"] and not (re.fullmatch(r"\d{4}", v["year"]) and 1800 <= int(v["year"]) <= datetime.now().year): errs["year"] = "Enter a valid 4-digit year"
    if v["udyam"] and not UDYAM_RE.match(v["udyam"]): errs["udyam"] = "Format: UDYAM-MH-01-0000000"
    if v["cin"] and not re.fullmatch(r"[A-Z0-9/\-]{5,30}", v["cin"]): errs["cin"] = "Enter a valid CIN / registration number"
    if india and v["ifsc"] and not IFSC_RE.match(v["ifsc"]): errs["ifsc"] = "Enter a valid 11-character IFSC (e.g. HDFC0001234)"
    if v["acc_no"]:
        v["acc_no"] = re.sub(r"[\s-]", "", v["acc_no"])
        if not re.fullmatch(r"\d{9,18}", v["acc_no"]): errs["acc_no"] = "Account number must be 9 to 18 digits"
    if not v["agree"]: errs["agree"] = "Please accept the declaration to submit"
    return v, errs

def read_files(files):
    """Check the uploaded documents.  Returns ({key: (original_name, bytes)}, errors)."""
    out, errs = {}, {}
    for k in FILE_KEYS:
        f = files.get(k)
        if not f or not f.filename: continue
        name = secure_filename(f.filename) or k
        ext = os.path.splitext(name)[1].lower()
        data = f.read(MAX_FILE + 1)
        if ext not in EXT: errs[k] = "Only PDF, JPG or PNG files are allowed"
        elif len(data) > MAX_FILE: errs[k] = "File is too large (maximum 3 MB)"
        elif not data.startswith(EXT[ext]): errs[k] = "This file looks damaged or is not a real " + ext[1:].upper()
        else: out[k] = (name, data)
    return out, errs

def save_files(no, got):
    """Write the checked files into the private folder; returns the {key: info} map stored in the vendor record."""
    meta, folder = {}, os.path.join(VDIR, str(no))
    if got: os.makedirs(folder, exist_ok=True)
    for k, (name, data) in got.items():
        fn = f"{k}{os.path.splitext(name)[1].lower()}"
        with open(os.path.join(folder, fn), "wb") as fh: fh.write(data)
        meta[k] = {"name": name, "file": fn, "size": len(data)}
    return meta

def file_path(v, key):
    """Absolute path of one uploaded document of vendor record `v` (None if missing / unsafe)."""
    m = (v.get("files") or {}).get(key)
    if not m: return None
    p = os.path.abspath(os.path.join(VDIR, str(v["no"]), os.path.basename(m["file"])))
    return p if p.startswith(os.path.abspath(VDIR) + os.sep) and os.path.isfile(p) else None

def remove_files(no):
    shutil.rmtree(os.path.join(VDIR, str(int(no))), ignore_errors=True)

# ------------------------------------------------------------------ helpers shared by the admin pages / PDF
def ref(v):
    c = v.get("created"); return f"SST/VND/{c.strftime('%Y') if c else '----'}/{int(v.get('no') or 0):06d}"

def firm(v): return v.get("firm") or v.get("company") or "-"                 # older (short chatbot form) records use 'company' / 'name' / 'phone'
def contact(v): return v.get("contact") or v.get("name") or "-"
def mobile(v): return v.get("mobile") or v.get("phone") or "-"
def products(v): return v.get("products") or v.get("supplies") or "-"
