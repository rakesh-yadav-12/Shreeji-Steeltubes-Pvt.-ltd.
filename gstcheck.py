"""GST verification shared by the Request For Quote page, Customer Details form and Vendor Registration form.
The API key stays in .env (GST_API_KEY). Optional GST_API_URL = provider URL with {key} and {gstin} placeholders."""
import os, re, time, logging

GST_RX = r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]"
_GST_CACHE = {}   # gstin -> (time, result): same GSTIN is not charged twice within 24 h

def lookup(gstin):
    """-> {"ok": True, "name", "trade", "status", "addr"} | {"ok": False, "reason": "invalid"|"unavailable"|"off"}
    Only reason == "invalid" (GST number definitely not found) should block a customer. Limits / key / server problems never do."""
    import requests
    key = os.getenv("GST_API_KEY", "").strip()
    if not key: return {"ok": False, "reason": "off"}
    gstin = gstin.strip().upper()
    if not re.fullmatch(GST_RX, gstin): return {"ok": False, "reason": "invalid"}
    hit = _GST_CACHE.get(gstin)
    if hit and time.time() - hit[0] < 86400: return hit[1]
    url = os.getenv("GST_API_URL", "https://sheet.gstincheck.co.in/check/{key}/{gstin}").replace("{key}", key).replace("{gstin}", gstin)
    try:
        j = requests.get(url, timeout=8).json()
    except Exception:
        logging.exception("GST API failed"); return {"ok": False, "reason": "unavailable"}
    d = j.get("data") if isinstance(j.get("data"), dict) else (j.get("taxpayerInfo") if isinstance(j.get("taxpayerInfo"), dict) else None)
    if d and (d.get("lgnm") or d.get("tradeNam")) and j.get("flag", True) is not False and j.get("error") in (None, False):
        adr = d.get("pradr", {}).get("adr", "") if isinstance(d.get("pradr"), dict) else ""
        res = {"ok": True, "name": d.get("lgnm") or d.get("tradeNam"), "trade": d.get("tradeNam") or "", "status": d.get("sts") or "", "addr": adr}
    elif j.get("flag") is False or j.get("error") is True:
        msg = str(j.get("message") or "").lower()
        # 'not found / invalid' is a definite answer; limits / auth / server problems are NOT the customer's fault -> don't block them
        res = {"ok": False, "reason": "invalid" if ("not found" in msg or "invalid" in msg or "no record" in msg) and "key" not in msg and "limit" not in msg else "unavailable"}
        if res["reason"] == "unavailable": logging.warning("GST API said: %s", j.get("message"))
    else:
        res = {"ok": False, "reason": "unavailable"}
    if res["ok"] or res["reason"] == "invalid": _GST_CACHE[gstin] = (time.time(), res)
    return res
