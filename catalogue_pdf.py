"""Builds the professional Company Catalogue PDF  ->  catalog/catalogue/Shreeji_Company_Catalogue.pdf

Run   python catalogue_pdf.py   after editing COMPANY / PRODUCT_INFO below (or options.py for grades & standards).
The chatbot sends this file when a customer taps "Company Catalogue" (unless an admin has uploaded their own).
"""
import os
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, PageBreak, Paragraph,
                                Spacer, Table, TableStyle, Image, KeepTogether)
import options as OPT

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "static", "logo.png")
OUT = os.path.join(HERE, "catalog", "catalogue", "Shreeji_Company_Catalogue.pdf")   # picked up automatically by the chatbot

BLUE, ORANGE = colors.HexColor("#2E3F96"), colors.HexColor("#EE6A24")
LIGHT, DARK, GREY = colors.HexColor("#EEF1FB"), colors.HexColor("#1B2559"), colors.HexColor("#5B6385")
W, H = A4
M = 18 * mm

# ----------------------------------------------------------------- EDIT HERE
COMPANY = dict(
    name="Shreeji SteelTubes Pvt. Ltd.",
    tagline="House of Quality Steel Tubes",
    about=("Shreeji SteelTubes Pvt. Ltd. offers a wide range of steel pipes and hollow sections for construction, "
           "infrastructure, water and fluid transport and general engineering use. Our focus is consistent quality, "
           "dependable supply and prompt service to every customer."),
    # Fill these to print them on the last page (empty ones are skipped):
    address="", phone="", email="", website="",
)
PRODUCT_INFO = {
    "MS ERW Pipe": ("Electric resistance welded round pipes in mild steel, for structural, mechanical and "
                    "general fluid-conveyance use.", "Structures, scaffolding, water & gas lines, engineering"),
    "GI ERW Pipe": ("Galvanised round pipes with a zinc coating for added protection against corrosion.",
                    "Plumbing, water supply, irrigation, fencing, conduits"),
    "Square Hollow Section": ("Square tubular sections with uniform strength on all sides and a clean finish.",
                              "Steel structures, trusses, gates & grills, machine frames"),
    "Rectangular Hollow Section": ("Rectangular tubular sections giving high strength-to-weight ratio "
                                   "in load-bearing members.", "Roof trusses, columns, frames, body building"),
    "Large Dia Pipes": ("Large-diameter ERW pipes for heavy-duty conveyance and structural applications.",
                            "Water transmission, piling, industrial piping"),
    "Spiral Welded Pipes": ("Large-diameter pipes formed from helically wound steel coil for long, high-volume lines.",
                            "Water & sewage pipelines, piling, structural"),
}
# --------------------------------------------------------------------------

def st(name, size=10, bold=False, color=DARK, lead=None, align=0, **kw):
    return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                          leading=lead or size * 1.35, textColor=color, alignment=align, **kw)

def P(t, style): return Paragraph(escape(str(t)), style)
def logo(width):
    w, h = PILImage.open(LOGO).size
    return Image(LOGO, width=width, height=width * h / w)

# ------------------------------------------------------------ page decoration
def cover(c, doc):
    c.saveState()
    c.setFillColor(colors.white); c.rect(0, 0, W, H, stroke=0, fill=1)
    # blue block with diagonal edge
    p = c.beginPath(); p.moveTo(0, 0); p.lineTo(W, 0); p.lineTo(W, H * .56); p.lineTo(0, H * .43); p.close()
    c.setFillColor(BLUE); c.drawPath(p, stroke=0, fill=1)
    # orange stripe along the diagonal
    p = c.beginPath(); p.moveTo(0, H * .43); p.lineTo(W, H * .56); p.lineTo(W, H * .56 + 7); p.lineTo(0, H * .43 + 7); p.close()
    c.setFillColor(ORANGE); c.drawPath(p, stroke=0, fill=1)
    # tube cross-section motif
    cx, cy = W * .89, H * .10
    for r, a in ((78, .10), (58, .10), (38, .12)):
        c.setStrokeColor(colors.white); c.setStrokeAlpha(a); c.setLineWidth(10); c.circle(cx, cy, r, stroke=1, fill=0)
    c.setStrokeAlpha(1)
    # logo
    lw = W - 2 * M - 40 * mm; w, h = PILImage.open(LOGO).size
    c.drawImage(LOGO, M, H - 30 * mm - lw * h / w, width=lw, height=lw * h / w, mask="auto")
    # title
    c.setFillColor(ORANGE); c.rect(M, H * .335, 14 * mm, 3, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 38); c.drawString(M, H * .27, "COMPANY")
    c.drawString(M, H * .27 - 44, "CATALOGUE")
    c.setFont("Helvetica", 13); c.setFillColor(colors.HexColor("#D5DBF5"))
    c.drawString(M, H * .27 - 70, "ERW Pipes   |   Hollow Sections   |   Large Dia & Spiral Pipes")
    c.setFont("Helvetica-Oblique", 12); c.setFillColor(colors.white)
    c.drawString(M, 22 * mm, COMPANY["tagline"])
    c.restoreState()

def inner(c, doc):
    c.saveState()
    w, h = PILImage.open(LOGO).size; lw = 44 * mm
    c.drawImage(LOGO, M, H - 12 * mm - lw * h / w, width=lw, height=lw * h / w, mask="auto")
    c.setFont("Helvetica", 8.5); c.setFillColor(GREY); c.drawRightString(W - M, H - 17 * mm, "COMPANY CATALOGUE")
    c.setStrokeColor(ORANGE); c.setLineWidth(2); c.line(M, H - 22 * mm, W - M, H - 22 * mm)
    c.setFillColor(BLUE); c.rect(0, 0, W, 11 * mm, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.rect(0, 11 * mm, W, 1.2, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica", 8.5)
    c.drawString(M, 4.2 * mm, f"{COMPANY['name']}  |  {COMPANY['tagline']}")
    c.drawRightString(W - M, 4.2 * mm, f"Page {doc.page - 1}")
    c.restoreState()

# -------------------------------------------------------------------- content
def heading(text, sub=None):
    out = [P(text, st("h", 20, True, BLUE)), Spacer(1, 3), Table([[""]], colWidths=[16 * mm], rowHeights=[2.5],
           style=[("BACKGROUND", (0, 0), (-1, -1), ORANGE)], hAlign="LEFT")]
    if sub: out += [Spacer(1, 6), P(sub, st("s", 10, False, GREY, 14))]
    return out + [Spacer(1, 10)]

def product_card(i, name):
    desc, apps = PRODUCT_INFO.get(name, ("", ""))
    g = ", ".join(OPT.GRADES.get(name, OPT.GRADES["default"]))
    s = ", ".join(OPT.STANDARDS.get(name, OPT.STANDARDS["default"]))
    body = [P(f"{i:02d}", st("n", 20, True, ORANGE)), Spacer(1, 2), P(name, st("pn", 12.5, True, BLUE, 15)),
            Spacer(1, 4), P(desc, st("pd", 8.8, False, DARK, 12)), Spacer(1, 5),
            Paragraph(f"<font color='#EE6A24'><b>Applications:</b></font> {escape(apps)}", st("pa", 8.3, False, GREY, 11.5)),
            Spacer(1, 3),
            Paragraph(f"<font color='#EE6A24'><b>Grades:</b></font> {escape(g)}", st("pg", 8.3, False, GREY, 11.5)),
            Spacer(1, 3),
            Paragraph(f"<font color='#EE6A24'><b>Standards:</b></font> {escape(s)}", st("ps", 8.3, False, GREY, 11.5))]
    t = Table([[body]], colWidths=[(W - 2 * M - 8) / 2])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LINEABOVE", (0, 0), (-1, 0), 3, BLUE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                           ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t

def build():
    doc = BaseDocTemplate(OUT, pagesize=A4, title="Shreeji SteelTubes - Company Catalogue", author=COMPANY["name"])
    doc.addPageTemplates([
        PageTemplate("cover", [Frame(0, 0, 1, 1, id="x")], onPage=cover),
        PageTemplate("inner", [Frame(M, 17 * mm, W - 2 * M, H - 17 * mm - 28 * mm, id="f", leftPadding=0,
                                     rightPadding=0, topPadding=0, bottomPadding=0)], onPage=inner)])
    S = [NextPageTemplate("inner"), PageBreak()]

    # About
    S += heading("About Us", COMPANY["tagline"]) + [P(COMPANY["about"], st("b", 10.5, False, DARK, 16)), Spacer(1, 16)]
    hl = [("Wide Range", "ERW pipes, galvanised pipes, square & rectangular hollow sections, large dia and spiral pipes"),
          ("Quality Grades", "Multiple grades and standards to suit structural, mechanical and fluid applications"),
          ("Quick Response", "Share your requirement in our chat and our team gets back to you promptly")]
    cells = [[[P(a, st("ha", 11.5, True, BLUE)), Spacer(1, 3), P(b, st("hb", 8.8, False, GREY, 12))] for a, b in hl]]
    t = Table(cells, colWidths=[(W - 2 * M) / 3] * 3)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LINEBEFORE", (1, 0), (-1, -1), 2, ORANGE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                           ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    S += [t, Spacer(1, 22)]

    # Product range overview table
    S += heading("Our Product Range")
    rows = [[P("#", st("th", 9, True, colors.white)), P("Product", st("th", 9, True, colors.white)),
             P("Typical Applications", st("th", 9, True, colors.white))]]
    for i, n in enumerate([k for k in PRODUCT_INFO], 1):
        rows.append([P(f"{i:02d}", st("td", 9, True, ORANGE)), P(n, st("td", 9.5, True, BLUE)),
                     P(PRODUCT_INFO[n][1], st("td", 9, False, DARK, 12))])
    t = Table(rows, colWidths=[14 * mm, 55 * mm, W - 2 * M - 69 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLUE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                           ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#D5DBF5")),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    S += [t, PageBreak()]

    # Product detail cards (2 per row)
    S += heading("Product Details", "Available grades and standards for each product.")
    names = list(PRODUCT_INFO); cards = [product_card(i, n) for i, n in enumerate(names, 1)]
    grid = [[cards[j], cards[j + 1] if j + 1 < len(cards) else ""] for j in range(0, len(cards), 2)]
    g = Table(grid, colWidths=[(W - 2 * M) / 2] * 2)
    g.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    S += [g, PageBreak()]

    # How to order + contact
    S += heading("How to Place an Enquiry", "Tap Product Enquiry in our chat and keep these details ready:")
    steps = ["Product", "Size / NB / OD", "Thickness / Schedule", "Length", "Grade", "Standard", "Brand preference",
             "Quantity", "Delivery location", "Delivery date"]
    chips = [[Table([[P(f"{n}", st("c", 11, True, colors.white, align=1)), P(s, st("c2", 9.5, True, DARK))]],
                    colWidths=[9 * mm, 36 * mm], style=[("BACKGROUND", (0, 0), (0, 0), ORANGE), ("BACKGROUND", (1, 0), (1, 0), LIGHT),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (1, 0), (1, 0), 7)])
              for n, s in enumerate(steps[j:j + 3], j + 1)] for j in range(0, len(steps), 3)]
    for r in chips:
        while len(r) < 3: r.append("")
    t = Table(chips, colWidths=[(W - 2 * M) / 3] * 3)
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    S += [t, Spacer(1, 16)]

    S += heading("Contact Us")
    info = [("Address", COMPANY["address"]), ("Phone", COMPANY["phone"]), ("Email", COMPANY["email"]),
            ("Website", COMPANY["website"])]
    info = [(a, b) for a, b in info if b]
    if info:
        t = Table([[P(a, st("ci", 10, True, BLUE)), P(b, st("cv", 10))] for a, b in info], colWidths=[30 * mm, W - 2 * M - 30 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), LIGHT), ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#D5DBF5")),
                               ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                               ("LEFTPADDING", (0, 0), (-1, -1), 9)]))
        S.append(t)
    else:
        S.append(P("Choose \"Contact Details\" in our chat to get the right department's phone number and email.",
                   st("cc", 10.5, False, DARK, 16)))
    S += [Spacer(1, 22), Table([[P("Thank you for choosing Shreeji SteelTubes", st("ty", 13, True, colors.white, align=1))]],
          colWidths=[W - 2 * M], rowHeights=[16 * mm], style=[("BACKGROUND", (0, 0), (-1, -1), BLUE),
          ("LINEBELOW", (0, 0), (-1, -1), 3, ORANGE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])]
    doc.build(S)
    print("Created", OUT)

if __name__ == "__main__":
    build()
