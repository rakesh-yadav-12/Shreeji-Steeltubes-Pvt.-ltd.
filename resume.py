"""Job-application resumes.

Resumes are kept in the PRIVATE folder  resume_docs/  (never served publicly).  Only a logged-in admin / HR user
can preview or download them (see the /admin/jobs/<no>/resume routes in app.py).

Flow (web chat):  the applicant picks a file  ->  POST /job/resume  (stash(), returns a one-time token)
                  ->  the job form is submitted with that token  ->  claim() moves the file to resume_docs/<no>.<ext>
"""
import os, re, json, time, secrets, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RDIR = os.path.join(HERE, "resume_docs")
TMP = os.path.join(RDIR, "_tmp")

MAX_FILE = 5 * 1024 * 1024                                  # 5 MB (the app-wide request limit is 25 MB)
EXT = {".pdf": b"%PDF", ".doc": b"\xd0\xcf\x11\xe0", ".docx": b"PK\x03\x04"}      # allowed type -> real file signature
MIME = {".pdf": "application/pdf", ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,40}$")


def _purge_tmp(max_age=86400):
    """Remove half-finished uploads (applicant never pressed Submit) older than a day."""
    now = time.time()
    for p in glob.glob(os.path.join(TMP, "*")):
        try:
            if now - os.path.getmtime(p) > max_age: os.remove(p)
        except OSError: pass


def stash(fs):
    """Validate an uploaded FileStorage and keep it temporarily.  Returns (token, original_name, error)."""
    if not fs or not fs.filename: return "", "", "Please choose your resume file"
    name = os.path.basename(fs.filename.replace("\\", "/"))
    ext = os.path.splitext(name)[1].lower()
    if ext not in EXT: return "", "", "Only PDF, DOC or DOCX files are allowed"
    data = fs.read(MAX_FILE + 1)
    if len(data) > MAX_FILE: return "", "", "File is too large (maximum 5 MB)"
    if not data.startswith(EXT[ext]): return "", "", "This file looks damaged or is not a real " + ext[1:].upper() + " file"
    os.makedirs(TMP, exist_ok=True); _purge_tmp()
    tok = secrets.token_urlsafe(18)
    with open(os.path.join(TMP, tok + ext), "wb") as f: f.write(data)
    with open(os.path.join(TMP, tok + ".json"), "w", encoding="utf-8") as f:
        json.dump({"name": re.sub(r"[^\w .()\-]", "_", name)[:120], "size": len(data)}, f)
    return tok, name, ""


def claim(token, no):
    """Move a stashed upload to its final private place for job application #no.
    Returns the metadata to save in the job document ({'file','name','size'}) or None."""
    if not token or not TOKEN_RE.match(token): return None
    src = next((p for p in glob.glob(os.path.join(TMP, token + ".*")) if not p.endswith(".json")), None)
    if not src: return None
    ext = os.path.splitext(src)[1].lower()
    if ext not in EXT: return None
    try:
        meta = json.load(open(os.path.join(TMP, token + ".json"), encoding="utf-8"))
    except Exception: meta = {}
    os.makedirs(RDIR, exist_ok=True)
    dst = os.path.join(RDIR, f"{no}{ext}")
    os.replace(src, dst)
    try: os.remove(os.path.join(TMP, token + ".json"))
    except OSError: pass
    return {"file": f"{no}{ext}", "name": meta.get("name") or f"resume{ext}", "size": meta.get("size") or os.path.getsize(dst)}


def file_path(job):
    """Absolute path of the resume of this job document, or None."""
    fn = ((job or {}).get("resume") or {}).get("file") or ""
    if not fn or fn != os.path.basename(fn): return None
    p = os.path.join(RDIR, fn)
    return p if os.path.isfile(p) else None


def ext_of(job):
    p = file_path(job)
    return os.path.splitext(p)[1].lower() if p else ""


def download_name(job):
    nm = re.sub(r"[^A-Za-z0-9]+", "_", str((job or {}).get("name") or "Applicant")).strip("_")[:40] or "Applicant"
    return f"Resume_{job.get('no')}_{nm}{ext_of(job)}"


def remove(no):
    for p in glob.glob(os.path.join(RDIR, f"{no}.*")):
        try: os.remove(p)
        except OSError: pass
