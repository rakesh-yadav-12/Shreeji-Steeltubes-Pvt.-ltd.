import os, sys, json
from pathlib import Path
from dotenv import load_dotenv
import requests

env = Path(__file__).resolve().parent / ".env"
load_dotenv(env, override=True)
key = (os.getenv("GST_API_KEY") or "").strip().strip("\"'").strip()
if not key:
    sys.exit("GST_API_KEY .env mein nahi hai")
print("key loaded: %s...%s (length %d)" % (key[:4], key[-4:], len(key)))
gst = sys.argv[1] if len(sys.argv) > 1 else "27AAEFF8716C1ZK"
url = os.getenv("GST_API_URL", "https://sheet.gstincheck.co.in/check/{key}/{gstin}").replace("{key}", key).replace("{gstin}", gst)
r = requests.get(url, timeout=15)
print("HTTP", r.status_code); print(r.text[:600])
import gstverify
print("gstverify._portal ->", gstverify._portal(gst))
