"""MongoDB layer. Collections: admins, enquiries, customers, contacts, documents, chat_state, counters."""
import os
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash
from pymongo import ReturnDocument

# --- Load .env from this file's directory (robust to CWD) ---
from dotenv import load_dotenv
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

_db = None

def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def norm(phone):
    d = "".join(ch for ch in str(phone) if ch.isdigit())
    return "91" + d if len(d) == 10 else d

def fmt_phone(phone):
    """Display a stored (digits-only) phone as '+91 9930988307'."""
    d = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(d) == 12 and d.startswith("91"):
        return "+91 " + d[2:]
    if len(d) == 10:
        return "+91 " + d
    return ("+" + d) if d else ""

def database():
    global _db
    if _db is None:
        uri = os.getenv("MONGO_URI")
        name = os.getenv("MONGO_DB", "srj_bot")

        # --- DEBUG (remove once it works) ---
        print("DEBUG .env path :", _ENV_PATH, "| exists:", _ENV_PATH.exists())
        print("DEBUG MONGO_URI :", (uri[:60] + "...") if uri else None)
        print("DEBUG MONGO_DB  :", name)
        # -------------------------------------

        if not uri:
            raise SystemExit(
                f"\n❌ MONGO_URI is not set.\n"
                f"   Expected a .env file at: {_ENV_PATH}\n"
                f"   Make sure the file is named exactly '.env' (not '.env.txt')\n"
                f"   and contains a line like:\n"
                f"   MONGO_URI=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/srj_whatsapp_bot\n"
            )

        if uri.startswith("mongomock"):            # only used for automated tests
            import mongomock
            client = mongomock.MongoClient()
        else:
            from pymongo import MongoClient
            client = MongoClient(uri, serverSelectionTimeoutMS=10000)
            try:
                client.admin.command("ping")
            except Exception as e:
                raise SystemExit(
                    f"\n❌ Cannot connect to MongoDB at {uri}\n   {e}\n"
                    "   Check: Atlas Network Access (add 0.0.0.0/0), DB user credentials,\n"
                    "   and that the cluster is running.\n"
                )
        _db = client[name]
    return _db

def init(admin_phone, admin_pass, admin_name):
    d = database()
    d.admins.create_index("phone", unique=True)
    # existing admins get a username (= their mobile number) so everybody can log in with a username too
    for a in d.admins.find({"$or": [{"username": {"$exists": False}}, {"username": None}, {"username": ""}]}):
        d.admins.update_one({"_id": a["_id"]}, {"$set": {"username": a["phone"]}})
    try: d.admins.create_index("username", unique=True, partialFilterExpression={"username": {"$type": "string"}})
    except Exception as e: print("username index:", e)
    d.enquiries.create_index("no", unique=True)
    d.customers.create_index("phone")
    if not d.admins.find_one({"phone": norm(admin_phone)}):
        d.admins.insert_one({"name": admin_name, "phone": norm(admin_phone),
                             "password_hash": generate_password_hash(admin_pass),
                             "username": norm(admin_phone), "active": True, "job_notify": False, "created": now_ist()})
    if d.contacts.count_documents({}) == 0:
        d.contacts.insert_many([{"department": x, "name": "Update in admin panel", "designation": "-",
                                 "phone": "-", "email": "-"} for x in
                                ["Sales", "Account", "Payment", "Godown", "Operation", "Admin"]])

def next_no(name="enquiry"):
    r = database().counters.find_one_and_update({"_id": name}, {"$inc": {"seq": 1}},
                                                upsert=True, return_document=ReturnDocument.AFTER)
    return r["seq"]

def sync_enquiry_counter():
    """After enquiries are deleted: move the 'enquiry' counter back to the highest remaining enquiry no
    (0 when none are left), so the next enquiry continues from there (all deleted -> next is #1)."""
    d = database()
    top = d.enquiries.find_one({}, {"no": 1}, sort=[("no", -1)])
    d.counters.update_one({"_id": "enquiry"}, {"$set": {"seq": int((top or {}).get("no") or 0)}}, upsert=True)

def get_state(key):
    r = database().chat_state.find_one({"_id": key})
    return (r.get("state", "MENU"), r.get("data", {})) if r else ("MENU", {})

def set_state(key, state, data):
    database().chat_state.update_one({"_id": key}, {"$set": {"state": state, "data": data}}, upsert=True)

def get_lang(key):
    """Chosen chat language for this conversation: 'en' (default) or 'hi'."""
    r = database().chat_state.find_one({"_id": key}, {"lang": 1})
    return (r or {}).get("lang") or "en"

def set_lang(key, lang):
    database().chat_state.update_one({"_id": key}, {"$set": {"lang": lang}}, upsert=True)

def set_utype(key, t):
    """What the visitor tapped after Hi: 'exist' (Existing Customer) or 'new' (New User). Decides which 'Your Details' block the enquiry page shows."""
    database().chat_state.update_one({"_id": key}, {"$set": {"utype": "exist" if t == "exist" else "new"}}, upsert=True)

def get_utype(key):
    r = database().chat_state.find_one({"_id": key}, {"utype": 1})
    return (r or {}).get("utype") or "new"

def ser(docs):
    """Add string 'id' to Mongo documents (for templates / URLs)."""
    out = []
    for x in docs:
        x = dict(x); x["id"] = str(x.get("_id", "")); out.append(x)
    return out