"""Builds (1) the company-intro image cards (static/intro/s*.png, swipe gallery) and (2) the SOCIAL-MEDIA ENGAGEMENT video
(static/intro/intro.mp4: how customers can chat / follow / call us directly) shown when a customer says Hi.
Run:  pip install pillow imageio-ffmpeg   then   python tools/make_intro_media.py
Edit the SLIDES text below (facts from www.shreejisteeltubes.com) and run again to refresh static/intro/."""
import os, subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "intro"); os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
BLUE, ORANGE, WHITE = (46, 63, 150), (238, 106, 36), (255, 255, 255)

def font(size, bold=True):
    names = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "arial.ttf"]
    for d in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "C:/Windows/Fonts", ""):
        for n in names:
            try: return ImageFont.truetype(os.path.join(d, n), size)
            except OSError: pass
    return ImageFont.load_default()

def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    return lines + [cur]

def logo_slide(path, sub):
    im = Image.new("RGB", (W, H), WHITE); d = ImageDraw.Draw(im)
    lg = Image.open(os.path.join(ROOT, "static", "logo.png")).convert("RGBA"); lg = lg.resize((860, int(860 * lg.height / lg.width)))
    im.paste(lg, ((W - lg.width) // 2, 150), lg)
    f = font(36, False); d.text(((W - d.textlength(sub, font=f)) / 2, 150 + lg.height + 50), sub, font=f, fill=BLUE)
    d.rectangle([0, H - 24, W, H], fill=ORANGE); im.save(path)

def text_slide(path, title, lines, fs=40):
    im = Image.new("RGB", (W, H), BLUE); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 18, H], fill=ORANGE); d.text((90, 90), title, font=font(68), fill=WHITE); d.rectangle([90, 195, 340, 204], fill=ORANGE)
    y, f = 255, font(fs, False)
    for ln in lines:
        for i, part in enumerate(wrap(d, ln, f, W - 270)):
            if i == 0: d.rectangle([90, y + 14, 106, y + 30], fill=ORANGE)
            d.text((135, y), part, font=f, fill=WHITE); y += int(fs * 1.45)
        y += 18
    im.save(path)

def steps_slide(path, title, steps, sub=""):
    """Numbered how-to slide: big number badges + short instructions."""
    im = Image.new("RGB", (W, H), BLUE); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 18, H], fill=ORANGE); d.text((90, 80), title, font=font(64), fill=WHITE); d.rectangle([90, 175, 340, 184], fill=ORANGE)
    if sub: d.text((90, 205), sub, font=font(30, False), fill=(190, 202, 245))
    y, f = 275, font(38, False)
    for n, txt in enumerate(steps, 1):
        lines = wrap(d, txt, f, W - 330); r = 34; cy = y + 22
        d.ellipse([100, cy - r, 100 + 2 * r, cy + r], fill=ORANGE, outline=WHITE, width=4)
        nf = font(38); d.text((100 + r - d.textlength(str(n), font=nf) / 2, cy - 24), str(n), font=nf, fill=WHITE)
        for ln in lines: d.text((200, y), ln, font=f, fill=WHITE); y += 54
        y += 40
    im.save(path)

# Social media / contact badges shown on the "Connect With Us" slide.
# Add more with (badge, colour, label, text) - e.g. ("ig", (214, 41, 118), "Instagram", "@yourhandle"),
# ("in", (10, 102, 194), "LinkedIn", "linkedin.com/company/..."), ("▶", (255, 0, 0), "YouTube", "youtube.com/@..."). Re-run this script.
SOCIAL_EXTRA = []
SOCIAL = [("www", ORANGE, "Website", "www.shreejisteeltubes.com"),
          ("f", (24, 119, 242), "Facebook", "facebook.com/SHREEJISTEELTUBES"),
          ("@", (88, 101, 190), "Email", "sales@shreejisteeltubes.com"),
          ("\u260E", (39, 174, 96), "Call us", "022 4171 8888  |  +91 99200 50742")] + SOCIAL_EXTRA

def connect_slide(path, title, rows):
    im = Image.new("RGB", (W, H), BLUE); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 18, H], fill=ORANGE); d.text((90, 90), title, font=font(68), fill=WHITE); d.rectangle([90, 195, 340, 204], fill=ORANGE)
    rh = min(112, (H - 240 - 30) // len(rows)); y = 240
    for badge, col, label, text in rows:
        cx, cy, r = 135, y + rh // 2 - 6, 36
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col, outline=WHITE, width=4)
        bf = font(22 if len(badge) > 2 else (30 if len(badge) > 1 else 40)); d.text((cx - d.textlength(badge, font=bf) / 2, cy - 22), badge, font=bf, fill=WHITE)
        d.text((205, y - 6), label, font=font(26, False), fill=(190, 202, 245)); d.text((205, y + 24), text, font=font(40), fill=WHITE)
        y += rh
    im.save(path)

GALLERY = [
    ("s1", "logo", "Distributor  •  Stockist  •  Supplier of Iron & Steel Products"),
    ("s2", "About Us", ["ISO 9001:2015 certified", "Mumbai-based leading Distributor, Stockist & Supplier of Iron & Steel products", "Everything under one roof - the widest range of steel tubes"]),
    ("s3", "Our Range", ["GI, MS & GP ERW Round Pipes", "Square, Rectangular & Circular Hollow Sections", "Seamless Pipes & Spiral Welded Pipes", "Other MS / Galvanised steel products in all sizes"]),
    ("s4", "Ready Stock", ["Approx. 50,000 sq. ft. storage at Kalamboli", "Kalamboli - the steel hub of Maharashtra", "Supply across Mumbai, Maharashtra & all major cities of India"]),
    ("s5", "Authorised Distributor", ["Jindal Pipes  •  Hitech Pipes  •  Rama Pipes", "Khanna Industrial Pipes  •  Uttam  •  Narmada  •  Asian"]),
    ("s6", "Industries We Serve", ["Construction & Heavy Equipment", "Infrastructure  •  Oil & Gas  •  Agriculture", "Machinery  •  Automotive & Transportation", "Renewable, Hydro & Nuclear Power Plants"]),
    ("s7", "Our Journey", ["1970 - Business journey begins as MODI BROTHERS", "2011 - Shreeji Steel Tubes starts as Stockist & Supplier of steel tubes", "Today - ISO 9001:2015 certified \"House of Quality Steel Tubes\""]),
    ("s8", "Explore Our Website", ["Product Catalogue  •  Certificates  •  Quality Assurance", "Photo Gallery  •  Documents  •  Our Clients", "Request for Quote  •  Vendor Registration  •  Career", "www.shreejisteeltubes.com"]),
    ("s9", "Visit Us", ["Head Office: 314/315, Hive 67, 3rd Floor, Poisar Gymkhana Road, Near Raghuleela Mall, Kandivali West, Mumbai 400067", "Kalamboli Stock Yard: Khedupada, Near New Taloja Bridge, Near Steel Chamber Kanta 2, Kalamboli, Raigad 410218"], 33),
    ("s10", "Connect With Us", SOCIAL, "connect"),
]

# ---- VIDEO: only social-media engagement - how a customer can reach us directly ----
WHATSAPP_NUMBER = ""      # optional, e.g. "+91 99XXX XXXXX" - shown on the chat slide when filled in (then re-run this script)
VIDEO = [
    ("v1", "logo", "Stay connected with us  •  Chat  •  Follow  •  Call"),
    ("v2", "Enquire in 3 Steps", ["Say Hi and pick your product", "Send Size, Thickness, Length & Quantity in one message", "Tap your delivery date - done! Our team will call you"],
     "steps", "Chat with us - no forms, no waiting" + (f"   •   WhatsApp {WHATSAPP_NUMBER}" if WHATSAPP_NUMBER else "")),
    ("v3", "Follow Us on Facebook", ["Open facebook.com/SHREEJISTEELTUBES", "Tap Like & Follow our page", "Message us anytime - we are one tap away"], "steps", "Stay updated with Shreeji SteelTubes"),
    ("v4", "Talk to Us Directly", [("\u260E", (39, 174, 96), "Call us", "022 4171 8888  |  +91 99200 50742"),
                                    ("@", (88, 101, 190), "Email", "sales@shreejisteeltubes.com")], "connect"),
    ("v5", "Get a Quote Online", ["Visit www.shreejisteeltubes.com", "Open \"Request For Quote\"", "Share your requirement - our team gets back to you"], "steps", "Quick quotes, from your phone"),
    ("v6", "Connect With Us", SOCIAL, "connect"),
    ("v7", "logo", "Follow  •  Chat  •  Call   |   www.shreejisteeltubes.com"),
]
VIDEO_SECONDS = {"v2": 6, "v3": 5, "v4": 4.5, "v5": 5, "v6": 5.5}          # seconds on screen (default 3.5)

def render(slides, outdir):
    os.makedirs(outdir, exist_ok=True); out = []
    for sl in slides:
        name, title, body = sl[0], sl[1], sl[2]; kind = sl[3] if len(sl) > 3 else None
        p = os.path.join(outdir, name + ".png"); out.append(p)
        if title == "logo": logo_slide(p, body)
        elif kind == "connect": connect_slide(p, title, body)
        elif kind == "steps": steps_slide(p, title, body, sl[4] if len(sl) > 4 else "")
        else: text_slide(p, title, body, kind if isinstance(kind, int) else 40)
    return out

render(GALLERY, OUT)                                          # swipe gallery images in the chat
paths = render(VIDEO, os.path.join(OUT, "video"))             # frames of the engagement video
F = 0.5                                                       # cross-fade seconds
durs = [VIDEO_SECONDS.get(sl[0], 3.5) for sl in VIDEO]
cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error"]
for p, L in zip(paths, durs): cmd += ["-loop", "1", "-t", str(L), "-i", p]
fg, last, acc = [], "[0]", 0.0
for k in range(1, len(paths)):
    acc += durs[k - 1] - F
    out = f"[v{k}]"; fg.append(f"{last}[{k}]xfade=transition=fade:duration={F}:offset={acc}{out}"); last = out
cmd += ["-filter_complex", ";".join(fg), "-map", last, "-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "27",
        "-movflags", "+faststart", os.path.join(OUT, "intro.mp4")]
subprocess.run(cmd, check=True)
print("done:", sorted(os.listdir(OUT)), sorted(os.listdir(os.path.join(OUT, "video"))))
