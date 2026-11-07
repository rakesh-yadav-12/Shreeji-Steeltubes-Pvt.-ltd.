"""Job Application page (web): form definition, validation and the private resume (PDF) storage.
The page itself is drawn by templates/home.html (buildJB) from form() - one single source for labels, order and 'required'."""
import os, re, shutil, hmac, hashlib
from werkzeug.utils import secure_filename
import options as OPT

HERE = os.path.dirname(os.path.abspath(__file__))
JDIR = os.path.join(HERE, "job_resumes")          # private folder - files are only served to a logged-in admin
MAX_FILE = 3 * 1024 * 1024                          # 3 MB
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

def F(name, label, type="text", req=False, ph="", options=None, **kw):
    d = dict(name=name, label=label, type=type, req=req, ph=ph); d.update(kw)
    if options: d["options"] = options
    return d

def form():
    return {"title": "Job Application", "heading": "Apply for a Job", "submit": "Submit Application",
            "note": "Fields marked * are required.",
            "sections": [
                {"title": "Your Details", "fields": [
                    F("name", "Your Name", req=True, ph="Full name", maxlen=80),
                    F("phone", "Mobile No.", "tel", True, ph="10-digit mobile", maxlen=18),
                    F("email", "Email", "email", ph="you@example.com", maxlen=120),
                    F("city", "Current City", ph="City", maxlen=60)]},
                {"title": "Job Details", "fields": [
                    F("position", "Position Applying For", "select", True, ph="Select position", options=OPT.JOB_POSITIONS),
                    F("qualification", "Qualification", ph="e.g. B.Com", maxlen=80),
                    F("experience", "Experience", ph="e.g. 3 years", maxlen=40),
                    F("expected_salary", "Expected Salary", ph="e.g. 25,000 / month", maxlen=40)]},
                {"title": "", "fields": [F("note", "About you / Remarks", "textarea", ph="Anything else we should know about you?", maxlen=500, full=True)]},
                {"title": "", "fields": [F("resume", "Upload Resume (PDF)", "file", True, accept=".pdf", full=True)]},
            ]}

def fields(): return [f for s in form()["sections"] for f in s["fields"]]

def _t(x, n, multi=False):
    s = str(x or "").replace("\r", "")
    s = "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in s.split("\n")) if multi else re.sub(r"\s+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()[:n]

def mobile10(x):
    d = re.sub(r"\D", "", str(x or ""))
    if len(d) == 12 and d.startswith("91"): d = d[2:]
    elif len(d) == 11 and d.startswith("0"): d = d[1:]
    return d if re.fullmatch(r"[6-9]\d{9}", d) else ""

def clean(raw):
    """Validate the text fields. Returns (values, errors)."""
    v, errs = {}, {}
    for f in fields():
        if f["type"] == "file": continue
        n = f["name"]; s = _t(raw.get(n), f.get("maxlen", 120), f["type"] == "textarea")
        if f["type"] == "select" and s and s not in f["options"]: s = ""
        v[n] = s
        if f["req"] and not s: errs[n] = "This field is required"
    if v["phone"]:
        m = mobile10(v["phone"])
        if m: v["phone"] = m
        else: errs["phone"] = "Enter a valid 10-digit mobile number"
    if v["email"] and not EMAIL_RE.match(v["email"]): errs["email"] = "Enter a valid email address"
    return v, errs

def read_resume(files):
    """Check the uploaded resume (must be a real PDF, max 3 MB). Returns ((name, bytes) | None, errors)."""
    f = files.get("resume")
    if not f or not f.filename: return None, {"resume": "Please upload your resume (PDF)"}
    name = secure_filename(f.filename) or "resume.pdf"
    data = f.read(MAX_FILE + 1)
    if os.path.splitext(name)[1].lower() != ".pdf": return None, {"resume": "Only a PDF file is allowed"}
    if len(data) > MAX_FILE: return None, {"resume": "File is too large (maximum 3 MB)"}
    if not data.startswith(b"%PDF"): return None, {"resume": "This file looks damaged or is not a real PDF"}
    return (name, data), {}

def save_resume(no, got):
    folder = os.path.join(JDIR, str(int(no))); os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "resume.pdf"), "wb") as fh: fh.write(got[1])
    return {"name": got[0], "file": "resume.pdf", "size": len(got[1])}

def file_path(j):
    """Absolute path of the resume of job record `j` (None if missing / unsafe)."""
    m = j.get("resume")
    if not isinstance(m, dict) or not m.get("file"): return None
    p = os.path.abspath(os.path.join(JDIR, str(j["no"]), os.path.basename(m["file"])))
    return p if p.startswith(os.path.abspath(JDIR) + os.sep) and os.path.isfile(p) else None

def remove_files(no): shutil.rmtree(os.path.join(JDIR, str(int(no))), ignore_errors=True)


# ---- public (no-login) resume links: /job-resume/<no>/<token>  (token = HMAC of the application no. with SECRET_KEY, so it cannot be guessed) ----
def link_token(no):
    key = (os.getenv("SECRET_KEY") or "srj-job-resume").encode()
    return hmac.new(key, f"job-resume:{int(no)}".encode(), hashlib.sha256).hexdigest()[:24]

def token_ok(no, token): return hmac.compare_digest(link_token(no), str(token or ""))

def public_links(no, base=None):
    """(preview_url, download_url) that open WITHOUT admin login. '' if PUBLIC_URL is not set."""
    base = (base if base is not None else os.getenv("PUBLIC_URL") or "").rstrip("/")
    if not base: return "", ""
    u = f"{base}/job-resume/{int(no)}/{link_token(no)}"
    return u, u + "?dl=1"


# ---- public (no-login) interview accept/decline links: /job/interview/<no>/<accept|decline>/<token> ----
# (token = HMAC of the application no. + action with SECRET_KEY, so one cannot be swapped for the other and cannot be guessed)
def interview_token(no, action):
    key = (os.getenv("SECRET_KEY") or "srj-job-resume").encode()
    return hmac.new(key, f"job-interview:{action}:{int(no)}".encode(), hashlib.sha256).hexdigest()[:24]

def interview_token_ok(no, action, token):
    return hmac.compare_digest(interview_token(no, action), str(token or ""))

def interview_links(no, base=None):
    """(accept_url, decline_url) the candidate taps in the interview-scheduled email. '' if no base URL known."""
    base = (base if base is not None else os.getenv("PUBLIC_URL") or "").rstrip("/")
    if not base: return "", ""
    return (f"{base}/job/interview/{int(no)}/accept/{interview_token(no, 'accept')}",
            f"{base}/job/interview/{int(no)}/decline/{interview_token(no, 'decline')}")


# ---- resume quick-look: read the PDF once and show education / skills inside the admin row (no need to open View / Download) ----
_SUM_CACHE = {}
_EDU_KW = re.compile(r"(b\.?\s?tech|b\.?\s?e\b|b\.?\s?com|b\.?\s?sc|b\.?\s?a\b|bba|bca|m\.?\s?com|m\.?\s?sc|mba|mca|m\.?\s?tech|diploma|graduat|class\s*(xii|x|12|10)|hsc|ssc|12th|10th|i\.?t\.?i)", re.I)
_HEAD = re.compile(r"^(academic|education|qualification|technical skills|skills|key skills|core skills|experience|work experience|projects?|certifications?|achievements?|summary|objective|profile|languages|interests|hobbies|declaration|personal)\b.{0,30}:?$", re.I)

def _pdf_text(path, pages=2):
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        t = "\n".join((p.extract_text() or "") for p in r.pages[:pages])
    except Exception:
        return ""
    return re.sub(r"[\u200b-\u200f\u2060\ufeff\xa0]", " ", t)

def _section(lines, names):
    out, on = [], False
    for ln in lines:
        s = ln.strip().strip(":").strip()
        is_head = len(s) <= 32 and "," not in s and (_HEAD.match(s) or ln.strip().endswith(":"))
        if is_head:
            on = any(s.lower().startswith(n) for n in names)
            continue
        if on and s: out.append(s)
    return out

def resume_summary(j):
    """{'edu': [..], 'skills': [..], 'exp': [..], 'snippet': str, 'pages': n}  - best-effort, from the uploaded PDF. Always safe to call."""
    p = file_path(j)
    if not p: return {}
    key = (j.get("no"), os.path.getmtime(p))
    if key in _SUM_CACHE: return _SUM_CACHE[key]
    txt = _pdf_text(p)
    lines = [re.sub(r"\s+", " ", l).strip(" ●•▪▫◦-–\t") for l in txt.split("\n")]
    lines = [l for l in lines if l]
    edu = [l for l in _section(lines, ("academic", "education", "qualification")) if _EDU_KW.search(l)]
    if not edu: edu = [l for l in lines if _EDU_KW.search(l)]
    edu = [re.sub(r"^course\s+college/school\s*%?\s*/?\s*cgpa\s*", "", l, flags=re.I) for l in edu]
    edu = [re.sub(r"\s*\d+(\.\d+)?\s*%?$", "", l).strip()[:70] for l in edu if l.strip()][:3]
    skills, seen = [], set()
    for l in _section(lines, ("technical skills", "key skills", "core skills", "skills")):
        l = l.split(":", 1)[1] if ":" in l[:30] else l
        for t in re.split(r"[,;|/]", l):
            t = t.strip(" .")
            if 1 < len(t) <= 24 and t.lower() not in seen: seen.add(t.lower()); skills.append(t)
    exp = _section(lines, ("work experience", "experience"))[:2]
    snippet = " ".join(lines)[:260]
    res = {"edu": edu, "skills": skills[:10], "exp": [e[:90] for e in exp], "snippet": snippet}
    _SUM_CACHE[key] = res
    return res


# ---- admin WORKFLOW (compulsory order): 1 resume reviewed -> 2 interview scheduled -> 3 candidate reply -> 4 final decision -> delete ----
def resume_reviewed(j):
    """Step 1 is done when an admin opened/downloaded the resume (or no resume file exists, so there is nothing to review)."""
    return bool(j.get("resume_viewed")) or not file_path(j)

def is_closed(j):
    """Process is finished: final decision taken, or the candidate declined the interview."""
    return bool(j.get("final_status")) or j.get("interview_status") == "Declined"
