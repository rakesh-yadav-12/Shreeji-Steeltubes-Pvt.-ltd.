"""WhatsApp confirmation to the CUSTOMER after an enquiry is submitted.

IMPORTANT (WhatsApp rule): a business can send a free-text message only if the customer wrote to the business
in the last 24 hours.  A customer who used the web chat (QR scan) has NOT messaged your WhatsApp number, so Meta
only delivers an *approved message template*.  Create one in Meta Business Manager -> WhatsApp -> Message templates
(category: Utility) with exactly 4 variables, e.g.

  Hello {{1}}, thank you for your enquiry #{{2}} with Shreeji SteelTubes for {{3}} ({{4}}).
  Our team will contact you shortly. 🙏

and put its name in .env:   WA_CONFIRM_TEMPLATE=enquiry_confirmation        WA_CONFIRM_TEMPLATE_LANG=en
Optional Hindi template:    WA_CONFIRM_TEMPLATE_HI=enquiry_confirmation_hi   (language code 'hi')
Without a template the bot still tries a normal text message (works only inside the 24-hour window).
Set WA_CONFIRM=0 to switch the confirmation off.  Result is stored on the enquiry (field wa_confirm) and shown in Admin.
"""
import os, re, threading
import whatsapp
from db import database, now_ist

TEXT = {
    "en": ("✅ *Enquiry #{no} received*\nHello {name}, thank you for contacting *Shreeji SteelTubes Pvt Ltd*.\n\n"
           "📋 *Your requirement*\n• Product: {product}\n• Size: {size}  |  Thickness: {thickness}\n• Length: {length}  |  Qty: {qty}\n"
           "• Delivery: {delivery_date}\n\nOur team will contact you shortly. 🙏"),
    "hi": ("✅ *पूछताछ #{no} प्राप्त हुई*\nनमस्ते {name}, *श्रीजी स्टीलट्यूब्स प्रा. लि.* से संपर्क करने के लिए धन्यवाद।\n\n"
           "📋 *आपकी आवश्यकता*\n• उत्पाद: {product}\n• साइज़: {size}  |  मोटाई: {thickness}\n• लंबाई: {length}  |  मात्रा: {qty}\n"
           "• डिलीवरी: {delivery_date}\n\nहमारी टीम जल्द ही आपसे संपर्क करेगी। 🙏"),
}


def enabled():
    return bool(os.getenv("WA_TOKEN") and os.getenv("WA_PHONE_NUMBER_ID")) and os.getenv("WA_CONFIRM", "1") != "0"


def customer_number(doc):
    d = re.sub(r"\D", "", str(doc.get("phone") or ""))
    if len(d) == 10: return "91" + d
    return d if 11 <= len(d) <= 15 else None


def _fields(doc):
    f = {k: (str(doc.get(k) or "-").replace("\n", " ")[:60]) for k in
         ("no", "name", "product", "size", "thickness", "length", "qty", "delivery_date")}
    n = len(doc.get("more_items") or [])
    if n: f["product"] = (f["product"] + f" (+{n} more)")[:60]
    return f


def send(doc, lang=None):
    """Send the confirmation now.  Returns (ok, message)."""
    lang = lang or doc.get("lang") or "en"
    to = customer_number(doc)
    if not to: return False, "customer has no valid mobile number"
    f = _fields(doc)
    tpl = os.getenv("WA_CONFIRM_TEMPLATE_HI") if lang == "hi" and os.getenv("WA_CONFIRM_TEMPLATE_HI") else os.getenv("WA_CONFIRM_TEMPLATE")
    if tpl:
        code = "hi" if (lang == "hi" and os.getenv("WA_CONFIRM_TEMPLATE_HI")) else os.getenv("WA_CONFIRM_TEMPLATE_LANG", "en")
        params = [{"type": "text", "text": f[k]} for k in ("name", "no", "product", "qty")]
        payload = {"to": to, "type": "template", "template": {"name": tpl, "language": {"code": code},
                   "components": [{"type": "body", "parameters": params}]}}
    else:
        payload = {"to": to, "type": "text", "text": {"body": TEXT.get(lang, TEXT["en"]).format(**f)}}
    ok, err = whatsapp.api_send(payload)
    if not ok and not tpl and "131047" in err:
        err += "  -> customer has not messaged you in the last 24h: create an approved template (see confirm.py)"
    return ok, err


def _job(doc):
    ok, err = send(doc)
    try:
        database().enquiries.update_one({"no": doc["no"]}, {"$set": {
            "wa_confirm": "sent" if ok else "failed", "wa_confirm_note": err[:400], "wa_confirm_at": now_ist()}})
    except Exception as e:                      # never break the customer's chat because of a log write
        print("confirm log error:", e)


def start(doc):
    """Called right after an enquiry is saved.  Returns 'queued' | 'in-chat' | 'off' | 'no-number' (also saved on the enquiry)."""
    if doc.get("source") == "whatsapp": st = "in-chat"        # customer is already chatting on WhatsApp and sees the summary there
    elif not enabled(): st = "off"
    elif not customer_number(doc): st = "no-number"
    else: st = "queued"
    database().enquiries.update_one({"no": doc["no"]}, {"$set": {"wa_confirm": st}})
    if st == "queued": threading.Thread(target=_job, args=(dict(doc),), daemon=True).start()
    return st
