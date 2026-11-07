import requests, os, contextvars
import i18n
URL = "https://graph.facebook.com/v20.0/{}/messages"
# When set (web chat mode), replies are collected here instead of being sent to WhatsApp
collector = contextvars.ContextVar("collector", default=None)
# Language of the conversation being handled ('en' / 'hi') - set by bot.handle(); every outgoing text is translated here
LANG = contextvars.ContextVar("lang", default="en")

def _translate(payload):
    """Return a copy of the payload with visible texts (body / caption) translated to the chat language."""
    if LANG.get() != "hi": return payload
    p = dict(payload); t = p["type"]
    if t == "text": p["text"] = {"body": i18n.tr(p["text"]["body"], "hi")}
    elif t in ("image", "video", "document"):
        p[t] = dict(p[t]); p[t]["caption"] = i18n.tr(p[t].get("caption", ""), "hi")
    return p

def _post(payload, extra=None):
    payload = _translate(payload)
    extra = i18n.tr_ui(extra, LANG.get()) if extra else extra
    box = collector.get()
    if box is not None:
        if payload["type"] == "text":
            box.append({"type": "text", "text": payload["text"]["body"], **(extra or {})})
        elif payload["type"] == "video":
            box.append({"type": "text", "text": payload["video"].get("caption", ""), "video": payload["video"]["link"]})
        elif payload["type"] == "image":
            box.append({"type": "text", "text": payload["image"].get("caption", ""), "image": payload["image"]["link"]})
        else:
            d = payload["document"]
            size = ""
            try:
                from urllib.parse import unquote
                _l = unquote(d["link"].split("?")[0]); _b = os.path.dirname(__file__)
                fp = os.path.join(_b, "catalog", *_l.split("/catalog-files/")[1].split("/")) if "/catalog-files/" in _l \
                     else os.path.join(_b, "uploads", os.path.basename(_l))
                b = os.path.getsize(fp); size = f"{b/1048576:.1f} MB" if b >= 1048576 else f"{max(1, round(b/1024))} KB"
            except OSError: pass
            box.append({"type": "doc", "url": d["link"], "name": d["filename"], "caption": d.get("caption", ""), "size": size})
        return
    pid, tok = os.getenv("WA_PHONE_NUMBER_ID"), os.getenv("WA_TOKEN")
    if not pid or not tok:
        print("[WA not configured] ->", payload); return
    r = requests.post(URL.format(pid), json={"messaging_product": "whatsapp", **payload},
                      headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    if r.status_code >= 300: print("WA error", r.status_code, r.text)

def send_text(to, body, **ui):
    """ui (web chat only; WhatsApp already gets numbered options in `body`): chips=[(label, value)], picker='date',
    ph='input placeholder', mode='tel', progress=[step, total, label]."""
    _post({"to": to, "type": "text", "text": {"body": body}}, {k: v for k, v in ui.items() if v})

def send_image(to, url, caption=""):
    _post({"to": to, "type": "image", "image": {"link": url, "caption": caption}})

def send_video(to, url, caption=""):
    _post({"to": to, "type": "video", "video": {"link": url, "caption": caption}})

def send_document(to, link, filename, caption=""):
    _post({"to": to, "type": "document", "document": {"link": link, "filename": filename, "caption": caption}})


# ---------------------------------------------------------------- direct API call (NOT the web-chat collector) - used for confirmations
def api_send(payload):
    """Send straight to WhatsApp Cloud API even while a web-chat request is running.  Returns (ok, error_text)."""
    pid, tok = os.getenv("WA_PHONE_NUMBER_ID"), os.getenv("WA_TOKEN")
    if not pid or not tok: return False, "WhatsApp API not configured (WA_TOKEN / WA_PHONE_NUMBER_ID)"
    try:
        r = requests.post(URL.format(pid), json={"messaging_product": "whatsapp", **payload},
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    except requests.RequestException as e:
        return False, f"network error: {e}"
    if r.status_code >= 300: return False, f"{r.status_code} {r.text[:300]}"
    return True, ""
