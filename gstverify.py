"""GST verification + automatic UC (unique customer) code.

resolve(gstin) is the ONE function the rest of the app calls. It returns a dict:

  {"ok": True,  "gst": "...", "uc_code": "UC00012", "existing": True/False,
   "name": "<legal/trade name or customer company>", "status": "Active", "source": "db|portal|cache"}
  {"ok": False, "error": "<message for the customer>", "temp": True/False}   # temp = service problem, not the customer's fault

Order of work:
  1. format + checksum check (offline, instant)
  2. EXISTING customer?  -> look the GST up in MongoDB and return the saved UC code (no portal call, no new code)
  3. NEW customer        -> verify on the GST portal through a GSP API (Appyflow), cache the answer,
                            then generate a unique UC code and remember it against that GSTIN.

.env settings (all optional except the key):
  GST_PROVIDER=gstincheck        # gstincheck (GSTIN validator) | appyflow | mock (mock = offline testing, never use live)
  GST_API_KEY=...                # API key of the chosen provider
  GST_API_URL=...                # optional (gstincheck): URL with {key} and {gstin}, default https://sheet.gstincheck.co.in/check/{key}/{gstin}
  GST_STRICT=1                   # 1 = a GST that cannot be verified is rejected (also when the API is down)
                                 # 0 = if the API is DOWN the enquiry is still accepted, but no UC code is generated
  GST_CACHE_DAYS=7               # re-use a portal answer for this many days
  UC_PREFIX=UC                   # UC code looks like UC00001
  UC_START=1                     # first number to use (set higher if codes up to UC0xxxx already exist)
"""
import os, re, logging
from datetime import timedelta
import requests
from pymongo.errors import DuplicateKeyError
from db import database, now_ist

GST_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_STATE_CODES = set(range(1, 39)) | {97, 99}


def clean(g):
    return re.sub(r"\s+", "", str(g or "")).upper()


def checksum_ok(g):
    """Official GSTIN check digit (mod-36). Catches typos without calling the portal."""
    if not GST_RE.match(g) or int(g[:2]) not in _STATE_CODES:
        return False
    total = 0
    for i, ch in enumerate(g[:14]):
        v = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return _CHARS[(36 - total % 36) % 36] == g[14]


# ------------------------------------------------------------------ GST portal (through a GSP API)
def _portal(gstin):
    """Returns {"found": bool, "active": bool, "name": str, "status": str} or raises RuntimeError (service problem)."""
    provider = os.getenv("GST_PROVIDER", "gstincheck").lower()
    if provider == "mock":                       # offline testing only: ...Z5 = active, anything else = not found
        if gstin.endswith("Z5"):
            return {"found": True, "active": True, "name": "MOCK TRADERS PVT LTD", "legal": "MOCK OWNER", "trade": "MOCK TRADERS PVT LTD", "status": "Active"}
        return {"found": False, "active": False, "name": "", "status": ""}
    key = os.getenv("GST_API_KEY", "").strip().strip("\"'").strip()
    if not key:
        raise RuntimeError("GST_API_KEY is not set in .env")
    if provider == "gstincheck":                 # GSTIN validator API: GET https://sheet.gstincheck.co.in/check/{key}/{gstin}
        return _portal_gstincheck(gstin, key)
    try:
        url = "https://appyflow.in/api/verifyGST"
        # Appyflow documents this as a POST with a JSON body {gstNo, key_secret}; fall back to GET once if POST is refused
        r = requests.post(url, json={"gstNo": gstin, "key_secret": key}, timeout=12)
        j = r.json()
        if isinstance(j, dict) and j.get("error") and re.search(r"key|secret", str(j.get("message", "")), re.I):
            r2 = requests.get(url, params={"gstNo": gstin, "key_secret": key}, timeout=12)
            j2 = r2.json()
            if isinstance(j2, dict) and not (j2.get("error") and re.search(r"key|secret", str(j2.get("message", "")), re.I)):
                r, j = r2, j2
    except Exception as e:
        raise RuntimeError(f"GST API unreachable: {e}")
    info = j.get("taxpayerInfo") if isinstance(j, dict) else None
    if info:
        status = str(info.get("sts") or info.get("status") or "")
        legal, trade = str(info.get("lgnm") or info.get("legalName") or "").strip(), str(info.get("tradeNam") or "").strip()
        return {"found": True, "active": status.lower() == "active", "name": trade or legal, "legal": legal, "trade": trade, "status": status}
    msg = str((j or {}).get("message", "")) if isinstance(j, dict) else ""
    # "invalid / not found" style answers = the GSTIN does not exist; anything else (key, quota, server) = service problem
    account_problem = r.status_code in (401, 402, 403, 429) or re.search(r"key|secret|limit|quota|credit|balance|subscription|plan|auth", msg, re.I)
    if not account_problem and r.status_code < 500 and re.search(r"invalid|not\s*found|no\s*record|does\s*not\s*exist", msg, re.I):
        return {"found": False, "active": False, "name": "", "status": ""}
    raise RuntimeError(f"GST API error: {r.status_code} {msg[:120]}")


def _portal_gstincheck(gstin, key):
    """GSTIN validator (sheet.gstincheck.co.in). Answer: {"flag": true, "message": "GSTIN found", "data": {"lgnm", "tradeNam", "sts", ...}}"""
    url = os.getenv("GST_API_URL", "https://sheet.gstincheck.co.in/check/{key}/{gstin}").replace("{key}", key).replace("{gstin}", gstin)
    try:
        r = requests.get(url, timeout=12)
        j = r.json()
    except Exception as e:
        raise RuntimeError(f"GST API unreachable: {e}")
    if not isinstance(j, dict):
        raise RuntimeError(f"GST API error: {r.status_code} unexpected answer")
    d = j.get("data") if isinstance(j.get("data"), dict) else None
    if d and j.get("flag", True) is not False and (d.get("lgnm") or d.get("tradeNam")):
        status = str(d.get("sts") or d.get("status") or "")
        legal, trade = str(d.get("lgnm") or "").strip(), str(d.get("tradeNam") or "").strip()
        return {"found": True, "active": status.lower() == "active", "name": trade or legal, "legal": legal, "trade": trade, "status": status}
    msg = str(j.get("message") or "")
    # key / limit / credit / server problems are a SERVICE problem; only a clear 'not found / invalid' means the GSTIN does not exist
    if r.status_code in (401, 402, 403, 429) or re.search(r"key|secret|limit|quota|credit|balance|subscription|plan|auth|expire", msg, re.I):
        raise RuntimeError(f"GST API account problem: {r.status_code} {msg[:120]}")
    if r.status_code < 500 and re.search(r"invalid|not\s*found|no\s*record|does\s*not\s*exist", msg, re.I):
        return {"found": False, "active": False, "name": "", "status": ""}
    raise RuntimeError(f"GST API error: {r.status_code} {msg[:120]}")


def _verify_cached(gstin):
    d = database()
    days = int(os.getenv("GST_CACHE_DAYS", "7") or 7)
    c = d.gst_cache.find_one({"_id": gstin})
    if c and c.get("checked") and c["checked"] > now_ist() - timedelta(days=days):
        return c, "cache"
    res = _portal(gstin)                         # may raise RuntimeError
    if res["found"]:                             # only store positive answers (a 'not found' must be re-checked next time)
        res.update(checked=now_ist())
        d.gst_cache.update_one({"_id": gstin}, {"$set": res}, upsert=True)
    return res, "portal"


# ------------------------------------------------------------------ UC code
def _new_uc():
    """NEXT UC code from the LIVE data: highest code saved in the customers collection + 1 (UC_START when there is none).
    Nothing is reserved when a GST number is only checked - a code exists only once a New User really saves their details."""
    d = database()
    start = int(os.getenv("UC_START", "1") or 1)
    prefix = os.getenv("UC_PREFIX", "UC")
    rx = re.compile(r"^" + re.escape(prefix) + r"(\d+)$")
    top = start - 1
    for c in d.customers.find({"uc_code": {"$regex": "^" + re.escape(prefix) + r"\d+$"}}, {"uc_code": 1}):
        m = rx.match(str(c.get("uc_code") or ""))
        if m: top = max(top, int(m.group(1)))
    return f"{prefix}{top + 1:05d}"


def _existing(gstin):
    """UC code of the New-User record saved in the customers collection for this GSTIN (live data). None if there is none."""
    c = database().customers.find_one({"gst": gstin, "via_exist": {"$ne": True}, "uc_code": {"$nin": ["", None, "-"]}}, sort=[("created", 1)])
    if c:
        return c["uc_code"], c.get("company") or c.get("name", "")
    return None


# ------------------------------------------------------------------ existing customer: details by UC code
UC_RE = re.compile(r"^[A-Z]{1,6}\d{3,9}$")


def clean_uc(u):
    return re.sub(r"\s+", "", str(u or "")).upper()


def _mobile10(x):
    d = re.sub(r"\D", "", str(x or ""))
    return d[-10:] if len(d) >= 10 else ""


def find_by_uc(uc):
    """Details saved when the customer FIRST registered as a new user (oldest saved record wins), looked up by UC code.
    -> {"uc_code","name","company","gst","email","mobile"} or None when the code is unknown."""
    u = clean_uc(uc)
    if not UC_RE.match(u):
        return None
    d = database()
    docs = list(d.customers.find({"uc_code": u, "via_exist": {"$ne": True}}).sort("created", 1).limit(20))      # only the records saved when the customer registered as a NEW USER (copies made by later Existing-Customer enquiries do not count)
    if not docs:      # a UC code works for an Existing Customer ONLY while a customer record saved at New User time still exists in the database (deleted from Admin -> Customers = no longer usable)
        return None

    def pick(k):
        return next((str(x.get(k)).strip() for x in docs if str(x.get(k) or "").strip() not in ("", "-")), "")
    mobile = next((m for m in (_mobile10(x.get("phone")) for x in docs) if m), "")
    return {"uc_code": u, "name": pick("name"), "company": pick("company"),
            "gst": pick("gst"), "email": pick("email"), "mobile": mobile}


def find_by_gst(gst):
    """Existing customer who forgot the UC code: GST number -> same record as find_by_uc. Never verifies on the portal / never creates a UC code.
    -> dict (see find_by_uc) or None when this GST has no UC code yet."""
    g = clean(gst)
    if not GST_RE.match(g):
        return None
    ex = _existing(g)
    return find_by_uc(ex[0]) if ex else None


def is_customer(gst):
    """True when a customer record with this GST already exists (a submitted enquiry saved it). A New User may register a GST number only once."""
    g = clean(gst)
    return bool(g) and database().customers.find_one({"gst": g, "via_exist": {"$ne": True}}) is not None


def mask_mobile(m):
    m = _mobile10(m)
    return m[:2] + "******" + m[-2:] if m else ""


def mask_email(e):
    e = str(e or "")
    if "@" not in e:
        return ""
    a, b = e.split("@", 1)
    return a[:1] + "***@" + b


# ------------------------------------------------------------------ main entry
def resolve(gstin):
    g = clean(gstin)
    if not checksum_ok(g) and os.getenv("GST_PROVIDER", "").lower() != "mock":
        return {"ok": False, "temp": False, "error": "Invalid GST number. Please check the 15 characters and try again."}
    if os.getenv("GST_PROVIDER", "").lower() == "mock" and not GST_RE.match(g):
        return {"ok": False, "temp": False, "error": "Invalid GST number. Please check the 15 characters and try again."}

    ex = _existing(g)                                           # EXISTING customer -> UC code straight from the database
    if ex:
        return {"ok": True, "gst": g, "uc_code": ex[0], "existing": True, "name": ex[1], "legal": ex[1],
                "trade": ex[1], "status": "Existing customer", "source": "db"}

    strict = os.getenv("GST_STRICT", "1") != "0"
    try:
        res, src = _verify_cached(g)
    except RuntimeError as e:
        logging.warning("GST verification failed: %s", e)
        if strict:
            return {"ok": False, "temp": True, "error": "GST verification is temporarily unavailable. Please try again in a few minutes."}
        return {"ok": True, "gst": g, "uc_code": "", "existing": False, "name": "", "status": "Not verified (service down)", "source": "none"}
    if not res["found"]:
        return {"ok": False, "temp": False, "error": "This GST number was not found on the GST portal. Please check and try again."}
    if not res["active"]:
        return {"ok": False, "temp": False, "error": f"This GST registration is not active on the GST portal (status: {res['status'] or 'unknown'})."}

    code = _new_uc()                                            # NEW customer, verified -> next UC code from the live data (saved with the customer when the enquiry is submitted)
    return {"ok": True, "gst": g, "uc_code": code, "existing": False, "name": res["name"], "legal": res.get("legal", ""),
            "trade": res.get("trade", ""), "status": res["status"], "source": src}
