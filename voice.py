"""Voice notes sent on WhatsApp -> text.

Uses OpenAI speech-to-text (understands Hindi, English and Hinglish).  Set in .env:
    OPENAI_API_KEY=sk-...
    STT_MODEL=whisper-1            (optional - e.g. gpt-4o-mini-transcribe)
Without a key the bot politely asks the customer to type instead.  (Web-chat microphone needs no key - it uses the browser.)
"""
import os, requests

GRAPH = "https://graph.facebook.com/v20.0/"


def enabled():
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("WA_TOKEN"))


def transcribe_whatsapp_audio(media_id):
    """Download the voice note from WhatsApp and return its text, or None if it could not be transcribed."""
    if not enabled(): return None
    try:
        h = {"Authorization": "Bearer " + os.getenv("WA_TOKEN")}
        meta = requests.get(GRAPH + str(media_id), headers=h, timeout=15).json()
        audio = requests.get(meta["url"], headers=h, timeout=30)
        if audio.status_code >= 300 or len(audio.content) > 20 * 1024 * 1024: return None
        r = requests.post("https://api.openai.com/v1/audio/transcriptions",
                          headers={"Authorization": "Bearer " + os.getenv("OPENAI_API_KEY")},
                          data={"model": os.getenv("STT_MODEL", "whisper-1")},
                          files={"file": ("voice.ogg", audio.content, meta.get("mime_type", "audio/ogg"))}, timeout=60)
        if r.status_code >= 300:
            print("STT error", r.status_code, r.text[:200]); return None
        return (r.json().get("text") or "").strip() or None
    except Exception as e:
        print("voice error:", e); return None
