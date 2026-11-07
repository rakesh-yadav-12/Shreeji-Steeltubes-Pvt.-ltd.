import io, os
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, Flowable, KeepTogether

LOGO = os.path.join(os.path.dirname(__file__), "static", "logo.png")
BLUE, ORANGE = colors.HexColor("#2E3F96"), colors.HexColor("#EE6A24")
SS = getSampleStyleSheet()

def _logo(width):
    w, h = PILImage.open(LOGO).size
    return Image(LOGO, width=width, height=width * h / w)

def _p(text, size=8, bold=False, color=colors.black):
    st = ParagraphStyle("x", parent=SS["Normal"], fontSize=size, leading=size + 2,
                        fontName="Helvetica-Bold" if bold else "Helvetica", textColor=color)
    return Paragraph(escape(str(text if text not in (None, "") else "-")).replace("\n", "<br/>"), st)

def _d(e):
    c = e.get("created"); return c.strftime("%d-%m-%Y %H:%M") if c else "-"

def _company_lines():
    try:
        import options as OPT
        return [l.replace("*", "").strip() for l in OPT.COMPANY_ADDRESS.splitlines() if l.strip()]
    except Exception:
        return []

W, H = A4
NAVY = colors.HexColor("#1F2A63")

def _page(canvas, doc):
    """Double border, faint watermark, RECEIVED stamp, footer - drawn on every page."""
    canvas.saveState()
    canvas.setStrokeColor(NAVY); canvas.setLineWidth(2.2); canvas.rect(22, 22, W - 44, H - 44)
    canvas.setLineWidth(0.6); canvas.rect(28, 28, W - 56, H - 56)
    # watermark
    canvas.saveState(); canvas.translate(W / 2, H / 2 - 30); canvas.rotate(35)
    canvas.setFillColor(colors.HexColor("#EEF0F8")); canvas.setFont("Helvetica-Bold", 78)
    canvas.drawCentredString(0, 0, "ORIGINAL"); canvas.restoreState()
    # footer
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(colors.HexColor("#444444"))
    canvas.drawCentredString(W / 2, 46, "This is a computer-generated acknowledgement receipt. It does not require a physical signature or seal.")
    canvas.drawCentredString(W / 2, 36, "Receipt of an enquiry does not constitute a quotation, order confirmation or contract.")
    canvas.drawRightString(W - 40, 36 - 0, f"Page {doc.page}")
    canvas.restoreState()

def _stamp(canvas, x, y, text, date):
    canvas.saveState(); canvas.translate(x, y); canvas.rotate(12)
    canvas.setStrokeColor(colors.HexColor("#B3261E")); canvas.setFillColor(colors.HexColor("#B3261E"))
    canvas.setLineWidth(2.2); canvas.roundRect(-52, -24, 104, 48, 6)
    canvas.setLineWidth(0.8); canvas.roundRect(-48, -20, 96, 40, 4)
    canvas.setFont("Helvetica-Bold", 15); canvas.drawCentredString(0, 2, text)
    canvas.setFont("Helvetica", 8); canvas.drawCentredString(0, -12, date)
    canvas.restoreState()

class _Stamp(Flowable):
    def __init__(self, date): super().__init__(); self.date = date; self.width, self.height = 120, 60
    def wrap(self, aw, ah): return 120, 60
    def draw(self): _stamp(self.canv, 60, 30, "RECEIVED", self.date)

def _qr(text, size=78):
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    w = qr.QrCodeWidget(text); b = w.getBounds(); bw, bh = b[2] - b[0], b[3] - b[1]
    d = Drawing(size, size, transform=[size / bw, 0, 0, size / bh, 0, 0]); d.add(w); return d

def _ref(e):
    c = e.get("created"); yr = c.strftime("%Y") if c else "----"
    return f"SST/ENQ/{yr}/{int(e.get('no') or 0):06d}"

def single(e):
    """Official acknowledgement receipt for ONE enquiry (customer download after the Thank-you popup + admin per-enquiry PDF)."""
    buf = io.BytesIO()
    ref = _ref(e); g = lambda k: e.get(k)
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=36, bottomMargin=58,
                            title=f"Acknowledgement Receipt {ref}", author="Shreeji SteelTubes Pvt. Ltd.")
    FW = W - 88
    # --- header: logo | company | (blank) ---
    head = Table([[_logo(120), [Paragraph("<b>SHREEJI STEELTUBES PVT. LTD.</b>", ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NAVY, alignment=1)),
                                Paragraph("House of Quality Steel Tubes", ParagraphStyle("s", fontName="Helvetica-Oblique", fontSize=9, leading=12, alignment=1, textColor=colors.HexColor("#555555")))]
                  + [Paragraph(escape(l), ParagraphStyle("a", fontName="Helvetica", fontSize=7.5, leading=9.5, alignment=1)) for l in _company_lines()]]],
                 colWidths=[135, FW - 135])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    title = Table([[_p("ACKNOWLEDGEMENT RECEIPT", 14, True, colors.white)], [_p("Receipt of Product Enquiry", 9, False, colors.white)]], colWidths=[FW])
    title.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    for r in title._cellvalues: r[0].style.alignment = 1
    # --- receipt meta (2 x 2) ---
    L = lambda t: _p(t, 8.5, True, NAVY); V = lambda t, s=10, b=False: _p(t, s, b)
    meta = Table([[L("Receipt / Reference No."), V(ref, 10.5, True), L("Date & Time of Receipt"), V(_d(e), 10)],
                  [L("Enquiry No."), V(f"#{g('no')}", 10.5, True), L("Mode of Submission"), V("Online (QR / Web Chat)" if g("source") != "whatsapp" else "WhatsApp")]],
                 colWidths=[120, FW / 2 - 120, 115, FW / 2 - 115])
    meta.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, NAVY), ("INNERGRID", (0, 0), (-1, -1), .4, colors.HexColor("#9AA3CC")),
                              ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF1FB")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EEF1FB")),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    # --- numbered particulars ---
    def block(title_, rows, start=1):
        data = [[_p("Sr.", 8.5, True, colors.white), _p("Particulars", 8.5, True, colors.white), _p("Details", 8.5, True, colors.white)]]
        for i, (a, b) in enumerate(rows, start): data.append([_p(i, 9), _p(a, 9, True, NAVY), _p(b, 9)])
        t = Table(data, colWidths=[30, 160, FW - 190], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#9AA3CC")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F6FB")]),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6)]))
        return [_p(title_, 10, True, NAVY), Spacer(1, 3), t, Spacer(1, 7)]
    story = [head, Spacer(1, 10), title, Spacer(1, 10), meta, Spacer(1, 12)]
    story += block("A.  DETAILS OF THE APPLICANT", [("Name of Customer", g("name")), ("Company / Firm", g("company")), ("GST Number", g("gst")), ("UC Code", g("uc_code")),
                                                    ("Portal Access", g("portal_access")), ("Contact No.", g("phone")), ("Email", g("email")), ("Representatives", g("reps"))])
    mi = e.get("more_items") or []
    story += block("B.  DETAILS OF THE ENQUIRY" + (f"  -  ITEM 1 OF {len(mi) + 1}" if mi else ""), [("Product", g("product")), ("Size / NB / OD", g("size")), ("Thickness / Schedule", g("thickness")), ("Length", g("length")),
                                                  ("Grade", g("grade")), ("Standard", g("standard")), ("Brand Preference", g("brand")), ("Quantity", g("qty")),
                                                  ("Required Delivery Date", g("delivery_date")), ("Remarks", g("remarks"))])
    for n, it in enumerate(mi, 2):          # "+ Add another product" items of the same enquiry
        story += block(f"B{n}.  ADDITIONAL REQUIREMENT  -  ITEM {n} OF {len(mi) + 1}",
                       [("Product", it.get("product")), ("Size / NB / OD", it.get("size")), ("Thickness / Schedule", it.get("thickness")), ("Length", it.get("length")),
                        ("Grade", it.get("grade")), ("Standard", it.get("standard")), ("Brand Preference", it.get("brand")), ("Quantity", it.get("qty")),
                        ("Required Delivery Date", it.get("delivery_date"))])
    # --- verification QR + stamp + signatory ---
    base = (os.getenv("PUBLIC_URL") or "").rstrip("/")
    qtxt = f"Shreeji SteelTubes Pvt. Ltd. | Receipt {ref} | Enquiry #{g('no')} | {_d(e)} | {g('name')}" + (f" | {base}" if base else "")
    dt = e.get("created").strftime("%d-%m-%Y") if e.get("created") else ""
    foot = Table([[_qr(qtxt), _Stamp(dt), [Spacer(1, 26), _p("______________________________", 9), _p("For Shreeji SteelTubes Pvt. Ltd.", 8.5, True, NAVY), _p("Authorised Signatory (system generated)", 7.5)]],
                  [_p("Scan to verify receipt details", 7.5), "", ""]], colWidths=[130, 150, FW - 280])
    foot.setStyle(TableStyle([("VALIGN", (0, 0), (-1, 0), "MIDDLE"), ("ALIGN", (0, 0), (0, -1), "LEFT"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    note = Table([[_p("Note: Please quote the Reference No. above in all further communication. Our sales team will review your requirement and contact you shortly. "
                      "Keep this receipt for your records.", 8.5)]], colWidths=[FW])
    note.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .6, NAVY), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [KeepTogether([note, Spacer(1, 12), foot])]
    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return buf.getvalue()

def listing(rows, title="Product Enquiries"):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    heads = ["#", "Date", "Name", "Contact", "Company", "Product", "Size", "Thk/Sch", "Length", "Grade", "Std",
             "Brand", "Qty", "Remarks", "Del. date", "Status"]
    widths = [22, 54, 58, 62, 40, 74, 52, 48, 44, 44, 44, 44, 44, 62, 56, 40]
    data = [[_p(h, 7, True, colors.white) for h in heads]]
    for e in rows:
        vals = [e["no"], _d(e), e["name"], e["phone"], e.get("company"), e["product"] + (f" (+{len(e['more_items'])} more)" if e.get("more_items") else ""), e["size"], e["thickness"], e["length"],
                e["grade"], e["standard"], e["brand"], e["qty"], e.get("remarks"), e["delivery_date"], e["status"]]
        data.append([_p(v, 7) for v in vals])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLUE), ("GRID", (0, 0), (-1, -1), .4, colors.lightgrey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6FC")]),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    head = Table([[_logo(150), [Paragraph("<b>SHREEJI STEELTUBES PVT. LTD.</b>", ParagraphStyle("lh", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NAVY)),
                                _p(f"{title}  ({len(rows)})", 14, True, ORANGE)]]], colWidths=[170, 500])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    doc.build([head, Spacer(1, 8), t])
    return buf.getvalue()


# ====================================================================== Vendor Registration Form (PDF copy)
def _vpage(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(NAVY); canvas.setLineWidth(2.2); canvas.rect(22, 22, W - 44, H - 44)
    canvas.setLineWidth(0.6); canvas.rect(28, 28, W - 56, H - 56)
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(colors.HexColor("#444444"))
    canvas.drawCentredString(W / 2, 40, "Computer-generated copy of the online Vendor Registration Form. Registration does not constitute vendor approval, empanelment or an order.")
    canvas.drawRightString(W - 40, 40 - 11, f"Page {doc.page}")
    canvas.restoreState()

class _Tick(Flowable):
    """Tick-box drawn with lines (ticked = a check mark inside the square) - looks the same in every PDF viewer."""
    def __init__(self, on): super().__init__(); self.on = on; self.width = self.height = 11
    def wrap(self, aw, ah): return 11, 11
    def draw(self):
        c = self.canv; c.setStrokeColor(NAVY); c.setLineWidth(1); c.rect(0, 0, 11, 11)
        if self.on: c.setStrokeColor(colors.HexColor("#1a7f37")); c.setLineWidth(1.8); c.lines([(2, 5.5, 4.6, 2.4), (4.6, 2.4, 9.4, 9)])

def vendor(v):
    """The Vendor Registration Form as a PDF (same sections as the company's paper form) - customer copy + admin download."""
    import vendor as VN
    buf = io.BytesIO(); g = lambda k: v.get(k)
    FW = W - 88; ref = VN.ref(v)
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=36, bottomMargin=58,
                            title=f"Vendor Registration Form {ref}", author="Shreeji SteelTubes Pvt. Ltd.")
    L = lambda t: _p(t, 8, True, NAVY); V = lambda t, s=9, b=False: _p(t, s, b)
    ST = lambda extra=(): TableStyle([("BOX", (0, 0), (-1, -1), .8, NAVY), ("INNERGRID", (0, 0), (-1, -1), .4, colors.HexColor("#9AA3CC")),
                                      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4)] + list(extra))
    LAB = colors.HexColor("#EEF1FB")
    head = Table([[_logo(120), [Paragraph("<b>SHREEJI STEELTUBES PVT. LTD.</b>", ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NAVY, alignment=1)),
                                Paragraph("House of Quality Steel Tubes", ParagraphStyle("s", fontName="Helvetica-Oblique", fontSize=9, leading=12, alignment=1, textColor=colors.HexColor("#555555")))]
                  + [Paragraph(escape(l), ParagraphStyle("a", fontName="Helvetica", fontSize=7.5, leading=9.5, alignment=1)) for l in _company_lines()]]], colWidths=[135, FW - 135])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    title = Table([[_p("VENDOR REGISTRATION FORM", 14, True, colors.white)]], colWidths=[FW])
    title.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    title._cellvalues[0][0].style.alignment = 1
    dt = g("created").strftime("%d-%m-%Y") if g("created") else "-"
    meta = Table([[L("Date"), V(dt, 9.5, True), L("Vendor Code (office use)"), V(g("vendor_code"), 9.5, True)],
                  [L("Reference No."), V(ref, 9.5, True), L("Registration No."), V(f"#{g('no')}", 9.5, True)]], colWidths=[75, FW / 2 - 75, 118, FW / 2 - 118])
    meta.setStyle(ST([("BACKGROUND", (0, 0), (0, -1), LAB), ("BACKGROUND", (2, 0), (2, -1), LAB)]))

    def sec(num_title, rows):
        """rows: [(label, value)] shown two pairs per line; (label, value, True) = full-width line."""
        data, st, i, pend = [[_p(num_title, 9.5, True, colors.white), "", "", ""]], [("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), NAVY)], 1, None
        def solo(lb, val):          # label + value spanning the remaining 3 columns
            nonlocal i
            data.append([L(lb), V(val), "", ""]); st.extend([("SPAN", (1, i), (3, i)), ("BACKGROUND", (0, i), (0, i), LAB)]); i += 1
        for r in rows:
            if len(r) > 2 and r[2]:
                if pend: solo(*pend); pend = None
                solo(r[0], r[1])
            elif pend:
                data.append([L(pend[0]), V(pend[1]), L(r[0]), V(r[1])]); st.extend([("BACKGROUND", (0, i), (0, i), LAB), ("BACKGROUND", (2, i), (2, i), LAB)]); i += 1; pend = None
            else: pend = r
        if pend: solo(*pend)
        t = Table(data, colWidths=[98, FW / 2 - 98, 98, FW / 2 - 98]); t.setStyle(ST(st))
        return t
    fm = VN.firm; addr = g("address") or "-"
    csz = " - ".join(x for x in (", ".join(x for x in (g("city"), g("state")) if x), g("pin")) if x) or "-"
    s1 = sec("1.  COMPANY INFORMATION", [("Name of Firm / Company", fm(v), True), ("Type of the Firm", g("constitution")), ("Type of Vendor", g("vtype")), ("Country", g("country") or "India"), ("Status of Company", g("cstatus")),
                                        ("Contact Person", VN.contact(v)), ("Designation", g("designation")), ("Registered Address", addr, True),
                                        ("City", g("city")), ("State", g("state")), ("PIN Code", g("pin")), ("Mobile No.", VN.mobile(v)), ("Landline", g("landline")),
                                        ("Email", g("email")), ("Website", g("website")), ("Year of Establishment", g("year"))])
    s2 = sec("2.  STATUTORY DETAILS", [("PAN No.", g("pan")), ("GST No.", g("gst")), ("MSME / Udyam Reg. No.", g("udyam")), ("CIN / Registration No.", g("cin"))])
    s3 = sec("3.  BANK DETAILS", [("Account Holder Name", g("acc_name")), ("Bank Name", g("bank")), ("Account No.", g("acc_no")), ("IFSC Code", g("ifsc")),
                                  ("Account Type", g("acc_type")), ("Branch Name & Address", g("branch"), True)])
    s4 = sec("4.  BUSINESS DETAILS", [("Products / Services Offered", VN.products(v), True), ("Major Clients / References", g("clients"), True),
                                      ("Annual Turnover (last FY)", g("turnover")), ("Payment Terms Offered", g("pay_terms"))])
    # 5. documents: tick-box per document (ticked = the file was uploaded with the form)
    files = g("files") or {}
    tick = lambda ok: _Tick(ok)
    d = list(VN.DOCS); rows5 = [[_p("5.  DOCUMENTS ENCLOSED", 9.5, True, colors.white), "", "", ""]]
    for a in range(0, len(d), 2):
        x, y = d[a], d[a + 1] if a + 1 < len(d) else None
        rows5.append([tick(x[0] in files), V(x[1]), tick(y[0] in files) if y else "", V(y[1]) if y else ""])
    s5 = Table(rows5, colWidths=[24, FW / 2 - 24, 24, FW / 2 - 24]); s5.setStyle(ST([("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ALIGN", (0, 1), (0, -1), "CENTER"), ("ALIGN", (2, 1), (2, -1), "CENTER")]))
    # 6. declaration + signature
    decl = ("I/We hereby declare that the information furnished above is true and correct to the best of my/our knowledge. "
            "I/We agree to inform of any changes and accept the terms and conditions of the company.")
    sg = VN.file_path(v, "signature"); sgimg = ""
    if sg and sg.lower().endswith((".png", ".jpg", ".jpeg")):
        try:
            iw, ih = PILImage.open(sg).size; k = min(150 / iw, 54 / ih); sgimg = Image(sg, width=iw * k, height=ih * k)
        except Exception: sgimg = ""
    if not sgimg: sgimg = _p("(signed online)" if g("agree") else "", 8)
    s6 = Table([[_p("6.  DECLARATION", 9.5, True, colors.white), "", "", ""], [_p(decl, 8.5), "", "", ""],
                [L("Authorised Signatory Name"), V(g("signatory")), L("Designation"), V(g("sig_desig"))],
                [L("Place"), V(g("place")), L("Date"), V(dt)],
                [L("Signature & Company Seal"), sgimg, "", ""]], colWidths=[98, FW / 2 - 98, 98, FW / 2 - 98], rowHeights=[None, None, None, None, 62])
    s6.setStyle(ST([("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("SPAN", (0, 1), (-1, 1)), ("SPAN", (1, 4), (-1, 4)),
                    ("BACKGROUND", (0, 2), (0, 4), LAB), ("BACKGROUND", (2, 2), (2, 3), LAB)]))
    od = g("office_date") or "-"
    s7 = Table([[_p("FOR OFFICE USE ONLY", 9.5, True, colors.white), "", "", "", "", ""],
                [L("Verified by"), V(g("verified_by")), L("Approved by"), V(g("approved_by")), L("Date"), V(od)]],
               colWidths=[62, FW / 3 - 62, 62, FW / 3 - 62, 40, FW / 3 - 40])
    s7.setStyle(ST([("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5b6490")), ("BACKGROUND", (0, 1), (0, 1), LAB), ("BACKGROUND", (2, 1), (2, 1), LAB), ("BACKGROUND", (4, 1), (4, 1), LAB)]))
    gap = Spacer(1, 8)
    story = [head, Spacer(1, 8), title, Spacer(1, 8), meta, gap, KeepTogether([s1]), gap, KeepTogether([s2]), gap, KeepTogether([s3]), gap,
             KeepTogether([s4]), gap, KeepTogether([s5]), gap, KeepTogether([s6]), gap, KeepTogether([s7])]
    doc.build(story, onFirstPage=_vpage, onLaterPages=_vpage)
    return buf.getvalue()

# ---------- Job Application Form: simple one-page form (same header as the company letterhead) ----------
def job(j):
    """Simple Job Application Form (PDF) for ONE application (admin page download)."""
    buf = io.BytesIO(); g = lambda k: j.get(k)
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=36, bottomMargin=40,
                            title=f"Job Application #{g('no')}", author="Shreeji SteelTubes Pvt. Ltd.")
    FW = W - 88
    head = Table([[_logo(120), [Paragraph("<b>SHREEJI STEELTUBES PVT. LTD.</b>", ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NAVY, alignment=1)),
                                Paragraph("House of Quality Steel Tubes", ParagraphStyle("s", fontName="Helvetica-Oblique", fontSize=9, leading=12, alignment=1, textColor=colors.HexColor("#555555")))]
                  + [Paragraph(escape(l), ParagraphStyle("a", fontName="Helvetica", fontSize=7.5, leading=9.5, alignment=1)) for l in _company_lines()]]],
                 colWidths=[135, FW - 135])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.4, NAVY), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    t_ = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=14, leading=18, alignment=1, textColor=NAVY)
    m_ = Table([[_p(f"Application No.: #{g('no')}", 9.5, True), _p(f"Date: {_d(j)}", 9.5, True)]], colWidths=[FW / 2, FW / 2])
    m_.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "RIGHT")])); m_._cellvalues[0][1].style.alignment = 2
    def block(title_, rows):
        t = Table([[_p(a, 9.5, True, colors.white), _p(b, 10)] for a, b in rows], colWidths=[165, FW - 165])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#4A5584")), ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#C9CFE6")),
                               ("LINEBELOW", (0, 0), (-1, -1), .5, colors.HexColor("#C9CFE6")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
        return [Spacer(1, 12), _p(title_, 11, True, colors.HexColor("#4A4A4A")), Spacer(1, 4), t]
    story = [head, Spacer(1, 12), Paragraph("JOB APPLICATION FORM", t_), Spacer(1, 8), m_]
    story += block("Your Details", [("Your Name", g("name")), ("Mobile No.", g("phone")), ("Email", g("email")), ("Current City", g("city"))])
    story += block("Job Details", [("Position Applying For", g("position")), ("Qualification", g("qualification")), ("Experience", g("experience")), ("Expected Salary", g("expected_salary"))])
    story += block("About you / Remarks", [("Remarks", g("note"))])
    rs = g("resume") if isinstance(g("resume"), dict) else {}
    if rs.get("name"):
        import job as _JOB; u, u_dl = _JOB.public_links(int(g('no') or 0))
        st = ParagraphStyle("rl", parent=SS["Normal"], fontSize=10, leading=15)
        txt = escape(rs["name"]) + (f" ({rs['size'] // 1024} KB)" if rs.get("size") else "")
        if u: txt += f'<br/><link href="{u}" color="#2E3F96"><u>Preview resume</u></link> &nbsp;|&nbsp; <link href="{u_dl}" color="#2E3F96"><u>Download resume</u></link>'
        t = Table([[_p("Resume (PDF)", 9.5, True, colors.white), Paragraph(txt, st)]], colWidths=[165, FW - 165])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#4A5584")), ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#C9CFE6")),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
        story += [Spacer(1, 12), _p("Upload Resume (PDF)", 11, True, colors.HexColor("#4A4A4A")), Spacer(1, 4), t]
    doc.build(story)
    return buf.getvalue()
