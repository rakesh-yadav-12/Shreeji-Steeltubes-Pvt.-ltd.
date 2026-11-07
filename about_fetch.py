"""Fetch the About Us details LIVE from the official website and cache them.

    https://www.shreejisteeltubes.com/about-us/

get_about() -> dict used by the web About Us page (/about/data) and by the WhatsApp text.
 * The page is downloaded at most once every ABOUT_TTL seconds (default 6 hours).
 * Every field is parsed separately; anything that cannot be read falls back to DEFAULT,
   so the bot never breaks if the website is down or its layout changes.
 * d["source"] is "live" when at least the main sections were read from the website, else "default".
"""
import os, re, time, threading
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

URL = os.getenv("ABOUT_URL", "https://www.shreejisteeltubes.com/about-us/")
TTL = int(os.getenv("ABOUT_TTL", str(6 * 3600)))
IMG = "https://www.shreejisteeltubes.com/wp-content/uploads/"

# ---- built-in copy of the website text (used only if the live fetch fails) ----
DEFAULT = {
    "tagline": "We are committed to provide smooth & superior quality supply to all our customers !",
    "intro": [
        'M/s. Shreeji SteelTubes Pvt Ltd (ISO 9001:2015) is a leading Distributor, Stockist, and Supplier of premium Iron & Steel products, based in Mumbai. With a commitment to excellence, we take pride in being recognized as the "House of Quality Steel Tubes™", offering a comprehensive range of high-quality steel solutions under one roof.',
        "With an expansive 94,000 sq. ft. storage facility located in Kalamboli, Maharashtra's premier steel hub, we have the capability to fulfill large-scale orders efficiently. Our strategic location and vast inventory allow us to deliver high-quality steel products in desired sizes and quantities across Mumbai, Maharashtra, and all major regions of India."],
    "range": ["GI Pipe, MS Pipe, GP Pipe",
              "Structural Hollow Sections (Circular (CHS), Square (SHS) & Rectangular (RHS) - MS YST210 / YST310 / YST355) & GI Both",
              "Seamless Pipes", "Spiral Welded Pipes (H-Saw Pipe) & L-Saw Pipe",
              "MS Structure, MS Plate, MS Sheet, Colour Coated Profile Sheet & Galvanised Sheet"],
    "partners": ["Jindal Pipes Ltd.", "Maharashtra Seamless Ltd.", "Tata Steel Ltd.", "Hitech Pipes Ltd. Hitech Saw Pvt Ltd.",
                 "Jindal Steel & Power Ltd.", "Narmada Tubes Pvt Ltd. Asian Mills Pvt Ltd.", "Asian Tubes Pvt Ltd.",
                 "Rama Pipes Ltd.", "Khanna Industrial Pipes Pvt. Ltd."],
    "rangeLead": "We provide a wide selection of steel tubes and related products to meet diverse industry requirements, including:",
    "partnersLead": "We are authorized distributors of some of the most reputed steel manufacturers, including:",
    "trust": "At Shreeji SteelTubes Pvt Ltd, our customer-focused approach, extensive inventory, and strong industry relationships make us a trusted and reliable name in the steel industry.",
    "others": "Additionally, we collaborate with Surya Prakash Pipes, Goel Pipes, and JCO Gas Line Ltd. to meet specific customer needs.",
    "closing": "Your One-Stop Destination for Quality Steel Tubes!",
    "history": [["", "Our business journey was started in year 1970 when Mr. Navnit P. Modi and his brother cum partner Mr. Rohit P. Modi started as a procurement consultant & agents for steel tubes in Mumbai. They established a firm called MODI BROTHERS. The two partners started the business with the goal to meet the need of customer with best quality service and professional ethics. Along with good business in this very competitive market they also earned high respect and reputation in market. Under the guidance of Shri Rohit P. Modi, his son Mr. Ronak Modi started Company M/S Shreeji Steel Tubes in September 2011 as a Stockiest & Supplier of steel tubes. In next 10 yrs. with his hard work, long term vision and innovative approach he managed this company's growth beyond expectation. Company has successfully achieved all targets that they set for and company also achieved the reputation of House of Quality Steel Tubes. During this glorifying journey, Shreeji Steel Tubes management has not only invested in building a huge inventory of steel, but also developed a team of highly result oriented staff competent enough to handle all situations and offer challenging project solutions to customers, in turn winning their trust. Shreeji Steel Tubes strong corporate governance, ethical practices, values, principles, integrity, focused employees and transparent business practices have all contributed to burgeoning of the company."]],
    "vmv": [["🎯 Vision", "Build for durability- We want to deliver something worth, that will endure the test of time. We will do this by relentlessly focusing on our customers' need, building high quality systems to serve them better & better with planning for long term scale and very skilled work force."],
            ["🚀 Mission", 'The prime mission of Shreeji Steel Tube is to meet the need of developing Indian economy, with high quality steel tubes, best quality service to customers with competitive price. With feet firmly set on the ground and our enthusiasm sky high, we are now more than ready to explore new avenues and further strengthen our presence in the industry.'],
            ["⚖️ Core Values", 'Not to do business of ethics but to do business with ethics. We are accountable by measuring ourselves against the highest standard of business ethics, integrity and fiscal responsibility.']],
    "mgmt": [
        ["Mr. Ronak Rohit Modi", "Managing Partner", IMG + "2021/07/Ronak-Rohit-Modi.jpg",
         "A young & dynamic entrepreneur who plays a role similar to the CEO of Shreeji Steel Tubes. Strategic planning & policies of purchase and sales, communication, financial & tax management, office management and employee management are key areas of his function."],
        ["Mr. Rohit Prabhudas Modi", "Managing Partner", IMG + "2021/07/Rohit-P-Modi.jpg",
         "With his knowledge and experience of the market for 40 years, he helps in all crucial functions of the organization. Stock & employee management of warehouses, customer grievances, pricing policies and employee welfare are vital areas of his function."]],
    "aboutImg": IMG + "2021/08/about-img-1.jpg",
}

_lock = threading.Lock()
_cache = {"t": 0.0, "data": None, "tried": 0.0}


# ----------------------------------------------------------------------------- parsing helpers
def _clean(s):
    s = (s or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()

def _find(L, pred, start=0):
    for i in range(start, len(L)):
        if pred(L[i]): return i
    return -1

def _heading(txt):
    """lower-case heading text, without bullets / punctuation"""
    return re.sub(r"[^a-z ]", "", txt.lower()).strip()

def _img_url(img):
    for a in ("data-src", "data-lazy-src", "data-orig-file", "src"):
        v = img.get(a)
        if v and not v.startswith("data:"): return urljoin(URL, v)
    return ""

def parse(html):
    """Return a dict with only the fields that could be read from the page."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "form"]): t.decompose()
    L = [x for x in (_clean(t) for t in soup.get_text("\n").split("\n")) if x]
    out = {}

    s = _find(L, lambda x: "committed to provide" in x.lower())
    if s < 0: return out
    e = _find(L, lambda x: x.lower().startswith("significantly pushed") or _heading(x) == "our services", s)
    body = L[s:e if e > s else len(L)]
    out["tagline"] = body[0]

    # ---- Our Product Range (heading may share a text node with its intro sentence)
    i_rng = _find(body, lambda x: x.lower().startswith("our product range"))
    i_tp = _find(body, lambda x: x.lower().startswith("trusted partnerships"))
    i_hist = _find(body, lambda x: _heading(x) == "history")
    i_vis = _find(body, lambda x: _heading(x) == "vision")
    i_mis = _find(body, lambda x: _heading(x) == "mission")
    i_core = _find(body, lambda x: _heading(x) in ("core values", "core value"))
    i_mgmt = _find(body, lambda x: _heading(x) == "management")

    if i_rng > 0:
        intro = [x for x in body[1:i_rng] if len(x) > 40]
        items = [re.sub(r"^[✔✓•\-\s]+", "", x) for x in body[i_rng:i_tp if i_tp > 0 else len(body)] if x[:1] in "✔✓"]
        items = [x for x in items if x]
        if items: out["range"] = items
        lead = re.sub(r"^our product range[:\s-]*", "", body[i_rng], flags=re.I).strip()
        if not lead and i_rng + 1 < len(body) and body[i_rng + 1][:1] not in "✔✓": lead = body[i_rng + 1]
        if len(lead) > 30: out["rangeLead"] = lead
        # paragraph after the ✔ list = second intro paragraph (94,000 sq. ft ...)
        after = [x for x in body[i_rng:i_tp if i_tp > 0 else len(body)] if x[:1] not in "✔✓" and len(x) > 80]
        after = [x for x in after if not x.lower().startswith("our product range")]
        if after: intro.append(after[-1])
        if intro: out["intro"] = intro

    # ---- Trusted Partnerships
    if i_tp > 0:
        end = i_hist if i_hist > i_tp else len(body)
        blk = body[i_tp:end]
        i_add = _find(blk, lambda x: x.lower().startswith("additionally"))
        pre = blk[:i_add] if i_add > 0 else blk
        lead, rest = "", []
        for x in pre[1:]:
            if "authorized distributors" in x.lower():
                m = re.search(r"^(.*?including:?)\s*(.*)$", x, flags=re.I)
                lead, tail = (m.group(1), m.group(2)) if m else (x, "")
                if tail: rest.append(tail)
            else: rest.append(x)
        if lead: out["partnersLead"] = lead
        pl = [x for x in rest if "|" in x] or [x for x in rest if re.search(r"(Ltd|Limited)\.?$", x)]
        if pl:
            parts = [p.strip() for p in " | ".join(pl).split("|") if p.strip()]
            if parts: out["partners"] = parts
        tr = _find(blk, lambda x: x.lower().startswith("at shreeji"))
        if tr >= 0: out["trust"] = blk[tr]
        if i_add >= 0: out["others"] = blk[i_add]
        cl = _find(blk, lambda x: x.lower().startswith("your one-stop"))
        if cl >= 0: out["closing"] = blk[cl]

    # ---- History -> timeline items (sentences grouped in 2s, year taken as label)
    def section(a, stops):
        if a < 0: return ""
        nxt = [i for i in stops if i > a]
        b = min(nxt) if nxt else len(body)
        return " ".join(body[a + 1:b]).strip()
    stops = [i for i in (i_hist, i_vis, i_mis, i_core, i_mgmt) if i >= 0]
    htxt = section(i_hist, stops)
    if htxt:
        sents = re.split(r"(?<![A-Z]\.)(?<!\bMr\.)(?<!\bMrs\.)(?<!\bMs\.)(?<!\bDr\.)(?<!\bPvt\.)(?<!\bLtd\.)(?<!\bM/s\.)(?<!\bsq\.)(?<=[.!?])\s+(?=[A-Z])", htxt)
        grp = [" ".join(sents[k:k + 2]) for k in range(0, len(sents), 2)]
        items = []
        for g in grp:
            m = re.search(r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+)?\b(19|20)\d{2}\b", g)
            items.append([m.group(0) if m else "", g])
        out["history"] = items

    vm = []
    for title, idx in (("🎯 Vision", i_vis), ("🚀 Mission", i_mis), ("⚖️ Core Values", i_core)):
        t = section(idx, stops)
        if t: vm.append([title, t])
    if vm: out["vmv"] = vm

    # ---- Management: "Mr. Name" / "Managing Partner" / description ; photos in document order
    if i_mgmt >= 0:
        people, cur = [], None
        for x in body[i_mgmt + 1:]:
            if re.match(r"^(Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s", x) and len(x) < 60:
                cur = [x, "", ""]; people.append(cur)
            elif cur is not None:
                if not cur[1] and len(x) < 40 and "." not in x: cur[1] = x
                else: cur[2] = (cur[2] + " " + x).strip()
        photos = [_img_url(i) for i in soup.find_all("img") if "modi" in (_img_url(i) or "").lower()]
        res = []
        for n, p in enumerate(people):
            d = re.sub(r",?\s*Age\s*\d+\s*,?", ",", p[2])           # ages go out of date -> not shown
            d = re.sub(r"\s+,", ",", re.sub(r"\s+", " ", d)).strip()
            res.append([p[0], p[1] or "Managing Partner", photos[n] if n < len(photos) else "", d])
        if res: out["mgmt"] = res

    im = [_img_url(i) for i in soup.find_all("img") if "about-img" in (_img_url(i) or "").lower()]
    if im: out["aboutImg"] = im[0]
    return out


# ----------------------------------------------------------------------------- public API
def _merge(live):
    d = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT.items()}
    for k, v in (live or {}).items():
        if v: d[k] = v
    for p, dp in zip(d["mgmt"], DEFAULT["mgmt"]):           # keep default photo when none was found live
        if not p[2]: p[2] = dp[2]
    d["source"] = "live" if live and len(live) >= 4 else "default"
    d["fetched_at"] = int(time.time())
    return d

def fetch_live():
    r = requests.get(URL, timeout=12, headers={"User-Agent": "Mozilla/5.0 (ShreejiBot About-Us sync)"})
    r.raise_for_status()
    return parse(r.text)

def get_about(force=False):
    now = time.time()
    with _lock:
        c = _cache
        if force and c["data"] and now - c["t"] < 60: return c["data"]            # a refresh re-reads the website, but at most once a minute
        if not force and c["data"] and now - c["t"] < TTL: return c["data"]
        if not force and c["data"] is None and now - c["tried"] < 60: return _merge(None)   # do not hammer the site while it is down
        c["tried"] = now
        try:
            c["data"], c["t"] = _merge(fetch_live()), now
        except Exception as e:
            print("[about_fetch] live fetch failed:", e)
            if c["data"] is None: return _merge(None)       # stale cache (if any) keeps being served
        return c["data"]


# ----------------------------------------------------------------------------- WhatsApp text versions
def wa_main(d):
    return ("*About Us*\n_" + d["tagline"] + "_\n\n" + "\n\n".join(d["intro"][:1]) + "\n\n*Our Product Range*\n" +
            "\n".join("- " + x for x in d["range"]) + "\n\n" + "\n\n".join(d["intro"][1:]) + "\n\n*Trusted Partnerships*\n" +
            ", ".join(d["partners"]) + "\n" + d["others"] + "\n\n_" + d["closing"] + "_")

def wa_history(d):
    return "*Our History*\n" + "\n\n".join((f"*{a}* - " if a else "") + b for a, b in d["history"])

def wa_vision(d):
    return "\n\n".join("*" + re.sub(r"^[^\w]+", "", a) + "*\n" + b for a, b in d["vmv"])

def wa_mgmt(d):
    return "*Management*\n\n" + "\n\n".join(f"*{n}* - {r}\n{t}" for n, r, _, t in d["mgmt"])
