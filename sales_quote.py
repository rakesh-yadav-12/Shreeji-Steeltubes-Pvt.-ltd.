"""Sales-person price flow (replaces the old automatic price mail to the customer).

FLOW
  1. Customer submits an enquiry (web / WhatsApp)           -> bot.submit() calls sales_quote.start(doc)
  2. SALES person gets a mail: enquiry details + for every product "AVAILABLE / NOT AVAILABLE" (read from the
     Google Sheet, see sheet_quote.py) + a button  "Write price & send to customer".
  3. Sales person writes the price and presses Send         -> the customer gets a "Price Quotation" mail at once.
     Two ways, both work together:
       a) Button in the mail -> opens /quote/<no>/<token> (private link) -> type price -> Send.
       b) (optional) simply REPLY to that mail and write the price in the reply. The bot reads the reply from the
          mailbox (IMAP) and mails the customer automatically.  Needs IMAP_* settings, see ENV_ADDITIONS.txt.

SETTINGS: Admin panel -> Settings (saved in MongoDB). The same names in .env are only the fallback.
  SALES_QUOTE=0        -> switch the whole feature off (old behaviour: price mail to customer straight from the sheet)
  (sales person email(s) are set in Admin -> Admins -> 'Sales mails' switch; SALES_MAIL in .env is optional)
  SALES_IMAP_POLL=1    -> also accept the price typed as a REPLY to the mail (needs IMAP_HOST/IMAP_USER/IMAP_PASS or SMTP_USER/SMTP_PASS)
  IMAP_HOST=imap.gmail.com   IMAP_USER / IMAP_PASS (default = SMTP_USER / SMTP_PASS)   SALES_POLL_SECONDS=30
Uses the same SMTP_* settings as mailer.py.
"""
import os, re, hmac, hashlib, smtplib, threading, time, imaplib, email, email.header
from email.message import EmailMessage
from email.utils import parseaddr, make_msgid
from html import escape
from db import database, now_ist
import sheet_quote

DECRYPT = lambda t: t           # app.py sets this to its password decrypt function (IMAP password is stored encrypted)
_CFG = {"at": 0, "doc": {}}


def cfg(key, default=""):
    """Setting from Admin -> Settings (saved in MongoDB, collection 'settings'); falls back to the .env value, then to default."""
    if time.time() - _CFG["at"] > 5:
        try: _CFG["doc"] = database().settings.find_one({"_id": "sales"}) or {}
        except Exception: _CFG["doc"] = {}
        _CFG["at"] = time.time()
    v = _CFG["doc"].get(key)
    if v not in (None, ""):
        return DECRYPT(v) if key == "IMAP_PASS" else v
    return os.getenv(key, default)


def refresh_cfg(): _CFG["at"] = 0


_NO_STOCK = re.compile(r"^\s*(0|0\.0+|no|nil|none|n/?a|na|out\s*of\s*stock|not\s*available|unavailable|-)\s*$", re.I)


# ------------------------------------------------------------------ settings / recipients
def smtp_ready():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


def enabled():
    return str(cfg("SALES_QUOTE", "1")) != "0" and smtp_ready()


def sales_emails():
    """Active admins (Admin -> Admins) whose 'Sales mails' switch is On and who have an email saved.
    SALES_MAIL in .env is only an optional extra (not needed)."""
    out = []
    def add(e):
        e = (e or "").strip()
        if e and "@" in e and e.lower() not in [x.lower() for x in out]: out.append(e)
    try:
        for a in database().admins.find({"active": True, "sales_notify": True}): add(a.get("email"))
    except Exception as ex: print("sales_quote admins:", ex)
    for e in cfg("SALES_MAIL", "").split(","): add(e)
    return out


def sales_phone():
    try:
        for c in database().contacts.find({"department": {"$regex": r"^\s*sales\s*$", "$options": "i"}}):
            p = (c.get("direct_line") or c.get("phone") or "").strip()
            if p and p != "-": return p
    except Exception: pass
    return ""


def token(no):
    key = (os.getenv("SECRET_KEY") or "srj-sales-quote").encode()
    return hmac.new(key, f"sales-quote:{int(no)}".encode(), hashlib.sha256).hexdigest()[:24]


def token_ok(no, t):
    return hmac.compare_digest(token(no), str(t or ""))


def link(no):
    base = (cfg("PUBLIC_URL") or "http://localhost:5000").rstrip("/")
    return f"{base}/quote/{int(no)}/{token(no)}"


# ------------------------------------------------------------------ availability (from the Google Sheet)
def items_of(doc):
    first = {k: doc.get(k, "-") for k in ("product", "size", "thickness", "length", "qty", "grade", "standard", "brand", "delivery_date")}
    return [first] + [dict(i) for i in (doc.get("more_items") or [])]


def availability(it):
    """-> (status, rows). status = 'available' | 'unavailable' | 'unknown' (sheet could not be read / no match)."""
    try:
        rows = sheet_quote.find_matches(it.get("product"), it.get("size"), it.get("thickness"))
    except Exception as e:
        return "unknown", [{"_err": str(e)[:120]}]
    if not rows: return "unknown", []
    for r in rows:
        st = (r.get("stock") or "").strip()
        if st and not _NO_STOCK.match(st): return "available", rows
    return "unavailable", rows


LABEL = {"available": "AVAILABLE ✅", "unavailable": "NOT AVAILABLE ❌", "unknown": "NOT FOUND IN STOCK SHEET ⚠️ (please check)"}


def check_all(doc):
    out = []
    for n, it in enumerate(items_of(doc), 1):
        st, rows = availability(it)
        out.append({"n": n, "item": it, "status": st, "rows": rows})
    return out


def _row_text(r):
    if r.get("_err"): return f"sheet error: {r['_err']}"
    price = r.get("price") or "-"; unit = r.get("unit") or ""
    return f"Stock: {r.get('stock') or '-'}  |  Sheet price: {price}{(' / ' + unit) if unit else ''}"


# ------------------------------------------------------------------ mail helpers
def _smtp_send(m):
    host, port = os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587"))
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as s:
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(); s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)


def _from():
    return os.getenv("SMTP_FROM") or os.getenv("SMTP_USER")


def _item_text(n, it):
    return (f"Item {n}: {it.get('product', '-')} | Size {it.get('size', '-')} | Thk {it.get('thickness', '-')} | "
            f"Length {it.get('length', '-')} | Qty {it.get('qty', '-')} | Grade {it.get('grade', '-')} | Std {it.get('standard', '-')}")


# ------------------------------------------------------------------ 1) mail to the SALES person
def _sales_text(doc, checks):
    L = [f"New enquiry #{doc['no']}  -  stock check", "",
         f"Customer : {doc.get('name', '-')}  ({doc.get('company') or '-'})",
         f"Phone    : {doc.get('phone', '-')}", f"Email    : {doc.get('email') or 'NOT GIVEN - call the customer'}", ""]
    for c in checks:
        L.append(_item_text(c["n"], c["item"]))
        L.append(f"   -> {LABEL[c['status']]}")
        for r in c["rows"][:3]: L.append("      " + _row_text(r))
    L += ["", "TO SEND THE PRICE TO THE CUSTOMER:",
          f"  1) Open: {link(doc['no'])}   (write the price and press Send)",
          "  2) OR just REPLY to this mail and write the price - it goes to the customer automatically."
          if imap_ready() else "", "", "- Shreeji SteelTubes Pvt. Ltd. chatbot (automatic mail)"]
    return "\n".join(L)


def _sales_html(doc, checks):
    colors = {"available": "#14753c", "unavailable": "#a52828", "unknown": "#9a6700"}
    rows = ""
    for c in checks:
        it = c["item"]
        extra = "".join(f"<div style='font-size:12px;color:#555'>{escape(_row_text(r))}</div>" for r in c["rows"][:3])
        rows += (f"<tr><td style='padding:8px;border:1px solid #ddd'>{c['n']}</td>"
                 f"<td style='padding:8px;border:1px solid #ddd'><b>{escape(str(it.get('product', '-')))}</b><br>"
                 f"Size {escape(str(it.get('size', '-')))} | Thk {escape(str(it.get('thickness', '-')))} | "
                 f"Length {escape(str(it.get('length', '-')))} | Qty {escape(str(it.get('qty', '-')))}<br>"
                 f"Grade {escape(str(it.get('grade', '-')))} | {escape(str(it.get('standard', '-')))}</td>"
                 f"<td style='padding:8px;border:1px solid #ddd;color:{colors[c['status']]};font-weight:bold'>{escape(LABEL[c['status']])}{extra}</td></tr>")
    reply = ("<p style='font-size:13px;color:#444'>Or simply <b>reply to this mail</b> and write the price - the customer gets it automatically.</p>"
             if imap_ready() else "")
    return (f"<div style='font-family:Arial,sans-serif;max-width:640px'>"
            f"<h3 style='margin:0 0 6px'>New enquiry #{doc['no']} - stock check</h3>"
            f"<p style='margin:0 0 10px;font-size:14px'><b>{escape(str(doc.get('name', '-')))}</b> ({escape(str(doc.get('company') or '-'))})<br>"
            f"📞 {escape(str(doc.get('phone', '-')))} &nbsp; ✉ {escape(str(doc.get('email') or 'NOT GIVEN - call the customer'))}</p>"
            f"<table style='border-collapse:collapse;font-size:13px;width:100%'><tr style='background:#f1f1f1'><th style='padding:8px;border:1px solid #ddd'>#</th>"
            f"<th style='padding:8px;border:1px solid #ddd;text-align:left'>Requirement</th><th style='padding:8px;border:1px solid #ddd;text-align:left'>Availability</th></tr>{rows}</table>"
            f"<p style='margin:18px 0'><a href='{escape(link(doc['no']))}' style='background:#14753c;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:bold'>"
            f"✍ Write price &amp; send to customer</a></p>{reply}"
            f"<p style='font-size:12px;color:#888'>Shreeji SteelTubes Pvt. Ltd. chatbot (automatic mail)</p></div>")


def send_to_sales(doc):
    to = sales_emails()
    if not to: return False, "no sales person set - Admin -> Admins: save an email and switch 'Sales mails' On"
    checks = check_all(doc)
    m = EmailMessage()
    m["Subject"] = f"[Enq#{doc['no']}] Stock check & price needed - {doc.get('product', '')} - {doc.get('name', '')}"
    m["From"] = _from(); m["To"] = ", ".join(to); m["Message-ID"] = make_msgid()
    m.set_content(_sales_text(doc, checks)); m.add_alternative(_sales_html(doc, checks), subtype="html")
    try:
        _smtp_send(m)
        summary = ", ".join(f"{c['n']}:{c['status']}" for c in checks)
        return True, f"sent to {', '.join(to)} ({summary})"
    except Exception as e:
        return False, str(e)


# ------------------------------------------------------------------ 2) mail to the CUSTOMER (when the sales person writes the price)
def _cust_text(doc, price_text, sender_name):
    L = [f"Dear {doc.get('name', '-')},", "",
         f"Thank you for your enquiry #{doc['no']} with Shreeji SteelTubes Pvt. Ltd.", "",
         "Your requirement:"]
    for n, it in enumerate(items_of(doc), 1): L.append("  " + _item_text(n, it))
    L += ["", "Our price / quotation:", "", price_text.strip(), "",
          "For any query please reply to this mail" + (f" or call {sales_phone()}." if sales_phone() else "."), "",
          "Regards,", sender_name or "Sales Team", "Shreeji SteelTubes Pvt. Ltd."]
    return "\n".join(L)


def send_to_customer(doc, price_text, reply_to=None, sender_name=""):
    to = (doc.get("email") or "").strip()
    if not to: return False, "customer has no email saved - call " + str(doc.get("phone", ""))
    if not (price_text or "").strip(): return False, "price text is empty"
    m = EmailMessage()
    m["Subject"] = f"Price Quotation - Enquiry #{doc['no']} - {doc.get('product', '')}"
    m["From"] = _from(); m["To"] = to
    if reply_to: m["Reply-To"] = reply_to
    m.set_content(_cust_text(doc, price_text, sender_name))
    try:
        _smtp_send(m)
        return True, f"sent to {to}"
    except Exception as e:
        return False, str(e)


def deliver(no, price_text, via, reply_to=None, sender_name=""):
    """Save the sales person's price on the enquiry and mail it to the customer. via = 'link' | 'reply'. Returns (ok, note)."""
    d = database()
    doc = d.enquiries.find_one({"no": int(no)})
    if not doc: return False, "enquiry not found"
    ok, note = send_to_customer(doc, price_text, reply_to, sender_name)
    d.enquiries.update_one({"no": int(no)}, {"$set": {
        "sq_price": price_text.strip()[:4000], "sq_price_via": via, "sq_price_at": now_ist(),
        "sq_customer_mail": "sent" if ok else "failed", "sq_customer_note": note[:400]}})
    return ok, note


# ------------------------------------------------------------------ entry point (called from bot.submit)
def _job(doc):
    try: ok, note = send_to_sales(doc); st = "sent" if ok else "failed"
    except Exception as e: ok, note, st = False, str(e), "error"
    try:
        database().enquiries.update_one({"no": doc["no"]}, {"$set": {"sq_sales_mail": st, "sq_sales_note": note[:400], "sq_sales_at": now_ist()}})
    except Exception as e: print("sales_quote log error:", e)


def start(doc):
    """'queued' | 'off' | 'no-recipient'  (saved on the enquiry as sq_sales_mail). Runs in a background thread."""
    if not enabled(): st = "off"
    elif not sales_emails(): st = "no-recipient"
    else: st = "queued"
    database().enquiries.update_one({"no": doc["no"]}, {"$set": {"sq_sales_mail": st}})
    if st == "queued": threading.Thread(target=_job, args=(dict(doc),), daemon=True).start()
    return st


# ------------------------------------------------------------------ 3) optional: price typed as a REPLY to the sales mail (IMAP)
def imap_ready():
    return str(cfg("SALES_IMAP_POLL", "0")) == "1" and bool(cfg("IMAP_HOST") and (cfg("IMAP_USER") or os.getenv("SMTP_USER"))
                                                             and (cfg("IMAP_PASS") or os.getenv("SMTP_PASS")))


_QUOTE_START = re.compile(r"^(on .+wrote:|on .+, .+ at .+|-{2,}\s*original message|-{2,}\s*forwarded|from:\s.+|sent from my|_{5,})", re.I)


def reply_text(msg):
    """Only what the sales person typed (text/plain part), without the quoted original mail / signature."""
    body = ""
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and "attachment" not in str(p.get("Content-Disposition", "")):
                body = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace"); break
    else:
        body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
    out = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(">") or _QUOTE_START.match(s): break
        out.append(line.rstrip())
    return "\n".join(out).strip()


def poll_once():
    host = cfg("IMAP_HOST")
    user = cfg("IMAP_USER") or os.getenv("SMTP_USER"); pw = cfg("IMAP_PASS") or os.getenv("SMTP_PASS")
    allowed = [e.lower() for e in sales_emails()]
    done = 0
    M = imaplib.IMAP4_SSL(host, int(cfg("IMAP_PORT", "993") or 993))
    try:
        M.login(user, pw); M.select("INBOX")
        typ, data = M.search(None, "UNSEEN", "SUBJECT", '"[Enq#"')
        for num in (data[0].split() if typ == "OK" and data and data[0] else []):
            typ, parts = M.fetch(num, "(RFC822)")        # fetching marks it as read, so it is never handled twice
            if typ != "OK": continue
            msg = email.message_from_bytes(parts[0][1])
            sender = parseaddr(msg.get("From", ""))[1].lower()
            mm = re.search(r"\[Enq#(\d+)\]", str(email.header.make_header(email.header.decode_header(msg.get("Subject", "")))))
            if not mm or sender not in allowed: continue                # only a listed sales person's reply is accepted
            no = int(mm.group(1)); text = reply_text(msg)
            if not text: continue
            mid = msg.get("Message-ID") or f"{no}-{num}"
            claimed = database().enquiries.find_one_and_update({"no": no, "sq_reply_ids": {"$ne": mid}}, {"$push": {"sq_reply_ids": mid}})
            if not claimed: continue
            ok, note = deliver(no, text, "reply", reply_to=sender, sender_name=parseaddr(msg.get("From", ""))[0])
            print(f"sales_quote: reply for enquiry #{no} -> customer mail {'sent' if ok else 'FAILED: ' + note}")
            done += 1
    finally:
        try: M.logout()
        except Exception: pass
    return done


def _poll_loop():
    while True:
        every = 30
        try:
            every = max(10, int(cfg("SALES_POLL_SECONDS", "30") or 30))
            if enabled() and imap_ready():          # re-checked every round, so Admin -> Settings changes work without a restart
                lock = database().counters.find_one_and_update(      # only ONE gunicorn worker polls at a time
                    {"_id": "sales_poll", "until": {"$lt": time.time()}}, {"$set": {"until": time.time() + every * 0.8}})
                if lock is None and not database().counters.find_one({"_id": "sales_poll"}):
                    try: database().counters.insert_one({"_id": "sales_poll", "until": time.time() + every * 0.8}); lock = True
                    except Exception: lock = None
                if lock: poll_once()
        except Exception as e:
            print("sales_quote poll error:", e)
        time.sleep(every)


def start_poller():
    """Called once per worker from app.py. The thread sleeps until 'Reply by mail' is switched on in Admin -> Settings."""
    threading.Thread(target=_poll_loop, daemon=True, name="sales-reply-poller").start()
