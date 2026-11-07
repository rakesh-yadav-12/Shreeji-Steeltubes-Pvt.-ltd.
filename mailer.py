"""Emails the submitted enquiry details (plain text, no attachment) to the admin(s) automatically, right after a customer submits an enquiry.

Only admins who are ACTIVE and have an email saved (Admin -> Admins -> set each admin's email) receive it.
Runs in a background thread (like confirm.py's WhatsApp confirmation) so the customer's chat never waits on it.

.env settings (see ENV_ADDITIONS.txt):
  SMTP_HOST, SMTP_PORT (587 = STARTTLS, 465 = SSL), SMTP_USER, SMTP_PASS, SMTP_FROM (optional, defaults to SMTP_USER)
  MAIL_NOTIFY=0            -> switch this feature off entirely
  MAIL_NOTIFY_EXTRA         -> extra, comma-separated email addresses that are always copied (people without an admin login)
Gmail: use an **App Password** (Google Account -> Security -> 2-Step Verification -> App passwords), a normal Gmail
password will NOT work. SMTP_HOST=smtp.gmail.com, SMTP_PORT=587.

Result is saved on the enquiry (field admin_mail: 'sent' | 'failed' | 'queued' | 'off' | 'no-recipient') and shown
in Admin -> Enquiries, with a manual "Send" / "Resend" button for 'failed' / 'off' / 'no-recipient'.
"""
import os, smtplib, threading
from email.message import EmailMessage
from db import database, now_ist


def enabled():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS")) and os.getenv("MAIL_NOTIFY", "1") != "0"


def admin_emails():
    """Every ACTIVE admin's email (Admin -> Admins) + MAIL_NOTIFY_EXTRA, de-duplicated, in order."""
    out = []
    for a in database().admins.find({"active": True}):
        e = (a.get("email") or "").strip()
        if e and e.lower() not in [x.lower() for x in out]: out.append(e)
    for e in (os.getenv("MAIL_NOTIFY_EXTRA", "")).split(","):
        e = e.strip()
        if e and e.lower() not in [x.lower() for x in out]: out.append(e)
    return out


def _item_block(it, n):
    """One extra product ('+ Add another product') formatted as plain text, item 2, 3, ..."""
    return (f"\nItem {n}\n"
            f"Product  : {it.get('product', '-')}\nSize     : {it.get('size', '-')}  |  Thickness: {it.get('thickness', '-')}\n"
            f"Length   : {it.get('length', '-')}  |  Qty: {it.get('qty', '-')}\nGrade    : {it.get('grade', '-')}  |  Standard: {it.get('standard', '-')}\n"
            f"Brand    : {it.get('brand') or '-'}\nDelivery : {it.get('delivery_date', '-')}\n")


def _body(doc):
    more_items = doc.get("more_items") or []
    n = len(more_items)
    more = f" (+{n} more product{'s' if n > 1 else ''} below)" if n else ""
    body = (f"New enquiry #{doc['no']} received on the website/WhatsApp chatbot.\n\n"
            f"Customer : {doc.get('name', '-')}\nCompany  : {doc.get('company') or '-'}\nGST No.  : {doc.get('gst') or '-'}\nUC Code  : {doc.get('uc_code') or '-'}\nPhone    : {doc.get('phone', '-')}\nEmail    : {doc.get('email') or '-'}\n\n"
            f"Item 1\n"
            f"Product  : {doc.get('product', '-')}{more}\nSize     : {doc.get('size', '-')}  |  Thickness: {doc.get('thickness', '-')}\n"
            f"Length   : {doc.get('length', '-')}  |  Qty: {doc.get('qty', '-')}\nGrade    : {doc.get('grade', '-')}  |  Standard: {doc.get('standard', '-')}\n"
            f"Brand    : {doc.get('brand') or '-'}\n"
            f"Delivery : {doc.get('delivery_date', '-')}\n{('Remarks  : ' + doc['remarks'] + chr(10)) if doc.get('remarks') and doc['remarks'] != '-' else ''}\n")
    for i, it in enumerate(more_items, 2): body += _item_block(it, i)
    body += "\n- Shreeji SteelTubes Pvt. Ltd. chatbot (automatic mail)"
    return body


def send(doc, to=None):
    """Send the submitted enquiry data (plain text, no attachment) to the given list of emails now (defaults to admin_emails()). Returns (ok, message)."""
    to = to if to is not None else admin_emails()
    if not to: return False, "no admin has an email saved (Admin -> Admins)"
    m = EmailMessage()
    m["Subject"] = f"New Enquiry #{doc['no']} - {doc.get('product', '')} - {doc.get('name', '')}"
    m["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER")
    m["To"] = ", ".join(to)
    m.set_content(_body(doc))
    host, port = os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as s:
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(); s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)
        return True, f"sent to {', '.join(to)}"
    except Exception as e:
        return False, str(e)


def _job(doc):
    ok, note = send(doc)
    try:
        database().enquiries.update_one({"no": doc["no"]}, {"$set": {
            "admin_mail": "sent" if ok else "failed", "admin_mail_note": note[:400], "admin_mail_at": now_ist()}})
    except Exception as e:                      # never break the customer's chat because of a log write
        print("mailer log error:", e)


def start(doc):
    """Called right after an enquiry is saved. Returns 'queued' | 'off' | 'no-recipient' (also saved on the enquiry)."""
    if not enabled(): st = "off"
    elif not admin_emails(): st = "no-recipient"
    else: st = "queued"
    database().enquiries.update_one({"no": doc["no"]}, {"$set": {"admin_mail": st}})
    if st == "queued": threading.Thread(target=_job, args=(dict(doc),), daemon=True).start()
    return st


# ---------- Job applications: the mail body IS the filled form (no extra text) -> ONLY the admin(s) linked for jobs + HR, resume via Preview / Download links (no attachment) ----------
def job_recipients():
    """Only ACTIVE admins who are linked for Job Application mails (Admin -> Admins -> 'Job application mails: On') and have an
    email saved, + HR_MAIL (comma-separated HR addresses in .env), de-duplicated. Unlike admin_emails() (enquiry PDFs, which go
    to every active admin with an email), job application mails go ONLY to admins explicitly linked for this."""
    out = []
    for a in database().admins.find({"active": True, "job_notify": True}):
        e = (a.get("email") or "").strip()
        if e and e.lower() not in [x.lower() for x in out]: out.append(e)
    for e in (os.getenv("HR_MAIL", "")).split(","):
        e = e.strip()
        if e and e.lower() not in [x.lower() for x in out]: out.append(e)
    return out


def _esc(x):
    from xml.sax.saxutils import escape
    return escape(str(x if x not in (None, "") else "-")).replace("\n", "<br>")


def _company_lines():
    try:
        import options as OPT
        return [l.strip() for l in OPT.COMPANY_ADDRESS.splitlines() if l.strip()]
    except Exception:
        return []


def _addr_html(l):                       # "*Head Office:* Office 314..." -> bold label, plain rest
    import re
    return re.sub(r"\*(.+?)\*", r"<b>\1</b>", _esc(l).replace("&amp;", "&amp;"))


def resume_links(doc):
    """(name, size_kb, preview_url, download_url) of the applicant's resume - public signed links, NO login needed."""
    import job as JOB
    rs = doc.get("resume") if isinstance(doc.get("resume"), dict) else {}
    if not rs: return "", 0, "", ""
    v, d = JOB.public_links(doc["no"])
    return rs.get("name") or "resume.pdf", (rs.get("size") or 0) // 1024, v, d


def _job_rows(doc):
    return [("Your Details", [("Your Name", doc.get("name")), ("Mobile No.", doc.get("phone")), ("Email", doc.get("email")), ("Current City", doc.get("city"))]),
            ("Job Details", [("Position Applying For", doc.get("position")), ("Qualification", doc.get("qualification")), ("Experience", doc.get("experience")), ("Expected Salary", doc.get("expected_salary"))]),
            ("About you / Remarks", [("Remarks", doc.get("note"))])]


_JOB_CSS = """
body{margin:0;padding:0;background:#fff;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}
table{border-collapse:collapse}
img{border:0;max-width:100%;height:auto}
@media only screen and (max-width:620px){
 .wrap{padding:6px 10px 16px !important}
 .logo{display:block !important;width:100% !important;text-align:center !important;padding:6px 0 2px !important}
 .logo img{width:120px !important;height:auto !important}
 .co{display:block !important;width:100% !important;text-align:center !important;padding-bottom:8px !important}
 .co-t{font-size:17px !important;line-height:1.25 !important}
 .addr{font-size:11.5px !important}
 .ttl{font-size:16px !important}
 .m1,.m2{display:block !important;width:100% !important;text-align:left !important;padding:2px 0 !important}
 .lab,.val{display:block !important;width:100% !important;box-sizing:border-box !important}
 .lab{border-bottom:0 !important;padding:7px 12px !important;font-size:12.5px !important}
 .val{font-size:15px !important;padding:9px 12px 11px !important}
 .btn{display:block !important;margin:0 0 8px 0 !important;text-align:center !important;padding:12px 16px !important;font-size:15px !important}
}
"""


def _job_html(doc, logo_cid):
    """The filled job form as a mobile-friendly (fluid, stacks on phones) email."""
    NAVY, LINE = "#1F2A63", "#c9cfe6"
    c = doc.get("created"); when = c.strftime("%d-%m-%Y %H:%M") if c else "-"
    addr = "".join(f'<div class="addr" style="font-size:12px;line-height:1.45;color:#222">{_addr_html(l)}</div>' for l in _company_lines())
    head = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-bottom:2px solid {NAVY}"><tr>'
            + (f'<td class="logo" width="150" valign="middle" style="padding:6px 10px 10px 0"><img src="cid:{logo_cid}" width="140" alt="Shreeji SteelTubes Pvt. Ltd." style="display:block;max-width:100%;height:auto"></td>' if logo_cid else "")
            + f'<td class="co" align="center" valign="middle" style="padding-bottom:8px"><div class="co-t" style="font-size:21px;font-weight:bold;color:{NAVY};letter-spacing:.5px">SHREEJI STEELTUBES PVT. LTD.</div>'
              f'<div style="font-size:13px;font-style:italic;color:#555;margin:2px 0 4px">House of Quality Steel Tubes</div>{addr}</td></tr></table>')
    row = lambda a, b, last=False: (f'<tr><td class="lab" width="34%" valign="top" style="background:#4a5584;color:#fff;font-size:13px;font-weight:bold;padding:9px 12px;border-bottom:1px solid #fff">{_esc(a)}</td>'
                                    f'<td class="val" valign="top" style="font-size:14px;color:#222;padding:9px 12px;border-bottom:1px solid {LINE};word-break:break-word;overflow-wrap:anywhere">{b}</td></tr>')
    body = ""
    for title, rows in _job_rows(doc):
        body += (f'<div style="margin:18px 0 6px;font-size:15px;font-weight:bold;color:#4a4a4a">{_esc(title)}</div>'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {LINE};border-collapse:collapse">'
                 + "".join(row(a, _esc(b)) for a, b in rows) + "</table>")
    nm, kb, view, dl = resume_links(doc)
    if nm:
        btn = lambda href, txt, bg: f'<a class="btn" href="{_esc(href)}" style="display:inline-block;margin:0 8px 6px 0;padding:9px 18px;background:{bg};color:#fff;font-size:13px;font-weight:bold;text-decoration:none;border-radius:4px">{txt}</a>'
        links = (btn(view, "&#128065; Preview", "#4a5584") + btn(dl, "&#11015; Download", "#0a1f5c")) if view else ""
        body += (f'<div style="margin:18px 0 6px;font-size:15px;font-weight:bold;color:#4a4a4a">Upload Resume (PDF)</div>'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {LINE};border-collapse:collapse">'
                 + row("Resume (PDF)", f'&#128196; {_esc(nm)}{f" ({kb} KB)" if kb else ""}<div style="margin-top:10px">{links}</div>') + "</table>")
    meta = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px"><tr>'
            f'<td class="m1" style="font-size:13px;color:#333"><b>Application No.:</b> #{_esc(doc.get("no"))}</td>'
            f'<td class="m2" align="right" style="font-size:13px;color:#333"><b>Date:</b> {_esc(when)}</td></tr></table>')
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="x-apple-disable-message-reformatting"><style>{_JOB_CSS}</style></head><body>'
            f'<div style="background:#fff;font-family:Arial,Helvetica,sans-serif;color:#222"><div class="wrap" style="max-width:720px;margin:0 auto;padding:8px 14px 20px">'
            f'{head}<div class="ttl" style="text-align:center;margin:14px 0 0;font-size:17px;font-weight:bold;color:{NAVY};letter-spacing:1px">JOB APPLICATION FORM</div>{meta}{body}</div></div></body></html>')


def _job_text(doc):                      # only for mail apps that cannot show HTML: the same form, as plain rows
    out = ["JOB APPLICATION FORM", f"Application No.: #{doc.get('no')}", ""]
    for title, rows in _job_rows(doc):
        out.append(title.upper()); out += [f"{a}: {b or '-'}" for a, b in rows]; out.append("")
    nm, kb, view, dl = resume_links(doc)
    if nm: out += ["UPLOAD RESUME (PDF)", f"Resume: {nm} ({kb} KB)"] + ([f"Preview : {view}", f"Download: {dl}"] if view else []) + [""]
    return "\n".join(out)


def send_job(doc, to=None):
    """Mail one job application: the mail body is the filled form, the resume is NOT attached - it opens through the Preview / Download links. Returns (ok, message)."""
    to = to if to is not None else job_recipients()
    if not to: return False, "no admin/HR email saved (Admin -> Admins, or HR_MAIL in .env)"
    m = EmailMessage()
    m["Subject"] = f"New Job Application #{doc['no']} - {doc.get('position', '')} - {doc.get('name', '')}"
    m["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER")
    m["To"] = ", ".join(to)
    if doc.get("email"): m["Reply-To"] = doc["email"]          # reply goes straight to the applicant
    m.set_content(_job_text(doc))
    logo = None
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png"), "rb") as fh: logo = fh.read()
    except Exception: pass
    m.add_alternative(_job_html(doc, "logo" if logo else ""), subtype="html")
    if logo: m.get_payload()[1].add_related(logo, maintype="image", subtype="png", cid="<logo>", disposition="inline")
    host, port = os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(); s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)
        return True, f"sent to {', '.join(to)}"
    except Exception as e:
        return False, str(e)


def _job_thread(doc):
    ok, note = send_job(doc)
    try:
        database().jobs.update_one({"no": doc["no"]}, {"$set": {
            "admin_mail": "sent" if ok else "failed", "admin_mail_note": note[:400], "admin_mail_at": now_ist()}})
    except Exception as e:
        print("job mail log error:", e)


def start_job(doc):
    """Called right after a job application is saved. Returns 'queued' | 'off' | 'no-recipient' (also saved on the application)."""
    if not enabled(): st = "off"
    elif not job_recipients(): st = "no-recipient"
    else: st = "queued"
    database().jobs.update_one({"no": doc["no"]}, {"$set": {"admin_mail": st}})
    if st == "queued": threading.Thread(target=_job_thread, args=(dict(doc),), daemon=True).start()
    return st


# ---------- Interview scheduled: mailed straight to the CANDIDATE (not the admin) with Accept / Decline buttons ----------
def _interview_html(doc, accept_url, decline_url, logo_cid):
    """'Your interview is fixed on <date> <time> - do you want to give the interview?' email, same mobile-friendly look as the job form mail."""
    NAVY, LINE = "#1F2A63", "#c9cfe6"
    addr = "".join(f'<div class="addr" style="font-size:12px;line-height:1.45;color:#222">{_addr_html(l)}</div>' for l in _company_lines())
    head = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-bottom:2px solid {NAVY}"><tr>'
            + (f'<td class="logo" width="150" valign="middle" style="padding:6px 10px 10px 0"><img src="cid:{logo_cid}" width="140" alt="Shreeji SteelTubes Pvt. Ltd." style="display:block;max-width:100%;height:auto"></td>' if logo_cid else "")
            + f'<td class="co" align="center" valign="middle" style="padding-bottom:8px"><div class="co-t" style="font-size:21px;font-weight:bold;color:{NAVY};letter-spacing:.5px">SHREEJI STEELTUBES PVT. LTD.</div>'
              f'<div style="font-size:13px;font-style:italic;color:#555;margin:2px 0 4px">House of Quality Steel Tubes</div>{addr}</td></tr></table>')
    row = lambda a, b: (f'<tr><td class="lab" width="34%" valign="top" style="background:#4a5584;color:#fff;font-size:13px;font-weight:bold;padding:9px 12px;border-bottom:1px solid #fff">{_esc(a)}</td>'
                        f'<td class="val" valign="top" style="font-size:14px;color:#222;padding:9px 12px;border-bottom:1px solid {LINE};word-break:break-word;overflow-wrap:anywhere">{_esc(b)}</td></tr>')
    details = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {LINE};border-collapse:collapse;margin-top:6px">'
               + row("Position", doc.get("position")) + row("Interview Date", doc.get("interview_date")) + row("Interview Time", doc.get("interview_time")) + "</table>")
    btn = lambda href, txt, bg: f'<a class="btn" href="{_esc(href)}" style="display:inline-block;margin:0 10px 8px 0;padding:11px 24px;background:{bg};color:#fff;font-size:14px;font-weight:bold;text-decoration:none;border-radius:4px">{txt}</a>'
    actions = ((btn(accept_url, "&#10003; Yes, I will attend", "#14753c") + btn(decline_url, "&#10007; No, I can't attend", "#a52828"))
               if accept_url and decline_url else
               '<div style="font-size:13px;color:#a52828">(Reply to this email to confirm - a direct link could not be generated.)</div>')
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="x-apple-disable-message-reformatting"><style>{_JOB_CSS}</style></head><body>'
            f'<div style="background:#fff;font-family:Arial,Helvetica,sans-serif;color:#222"><div class="wrap" style="max-width:720px;margin:0 auto;padding:8px 14px 20px">'
            f'{head}<div class="ttl" style="text-align:center;margin:14px 0 0;font-size:17px;font-weight:bold;color:{NAVY};letter-spacing:1px">INTERVIEW SCHEDULED</div>'
            f'<p style="font-size:15px;margin:18px 0 4px">Dear {_esc(doc.get("name"))},</p>'
            f'<p style="font-size:14.5px;line-height:1.55;margin:0 0 4px">Your interview for the position of <b>{_esc(doc.get("position"))}</b> has been fixed on '
            f'<b>{_esc(doc.get("interview_date"))}</b> at <b>{_esc(doc.get("interview_time"))}</b>.</p>'
            f'<p style="font-size:14.5px;line-height:1.55;margin:10px 0 2px"><b>Do you want to give the interview?</b></p>{details}'
            f'<div style="margin:20px 0 6px">{actions}</div>'
            f'<p style="font-size:12.5px;color:#666;margin-top:18px">Application No.: #{_esc(doc.get("no"))}</p>'
            f'</div></div></body></html>')


def _interview_text(doc, accept_url, decline_url):
    out = [f'Dear {doc.get("name")},', "",
           f'Your interview for the position of {doc.get("position")} has been fixed on {doc.get("interview_date")} at {doc.get("interview_time")}.',
           "", "Do you want to give the interview?"]
    if accept_url and decline_url: out += [f"Yes, I will attend : {accept_url}", f"No, I can't attend  : {decline_url}"]
    out += ["", f'Application No.: #{doc.get("no")}']
    return "\n".join(out)


def send_interview(doc, accept_url="", decline_url=""):
    """Mail the candidate that their interview is scheduled, with Accept / Decline links. Returns (ok, message)."""
    to = (doc.get("email") or "").strip()
    if not to: return False, "candidate has no email saved"
    m = EmailMessage()
    m["Subject"] = f'Interview Scheduled - {doc.get("position", "")} - Shreeji SteelTubes Pvt. Ltd.'
    m["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER")
    m["To"] = to
    m.set_content(_interview_text(doc, accept_url, decline_url))
    logo = None
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png"), "rb") as fh: logo = fh.read()
    except Exception: pass
    m.add_alternative(_interview_html(doc, accept_url, decline_url, "logo" if logo else ""), subtype="html")
    if logo: m.get_payload()[1].add_related(logo, maintype="image", subtype="png", cid="<logo>", disposition="inline")
    host, port = os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587"))
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(); s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")); s.send_message(m)
        return True, f"sent to {to}"
    except Exception as e:
        return False, str(e)


def _interview_thread(doc, accept_url, decline_url):
    ok, note = send_interview(doc, accept_url, decline_url)
    try:
        database().jobs.update_one({"no": doc["no"]}, {"$set": {
            "interview_mail": "sent" if ok else "failed", "interview_mail_note": note[:400], "interview_mail_at": now_ist()}})
    except Exception as e:
        print("interview mail log error:", e)


def start_interview(doc, accept_url="", decline_url=""):
    """Called right after HR schedules an interview. Returns 'queued' | 'off' | 'no-recipient' (also saved on the application)."""
    if not enabled(): st = "off"
    elif not (doc.get("email") or "").strip(): st = "no-recipient"
    else: st = "queued"
    database().jobs.update_one({"no": doc["no"]}, {"$set": {"interview_mail": st}})
    if st == "queued": threading.Thread(target=_interview_thread, args=(dict(doc), accept_url, decline_url), daemon=True).start()
    return st
