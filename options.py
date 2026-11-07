"""Suggestion lists used inside the Product Enquiry flow.

EDIT THIS FILE to match what Shreeji SteelTubes actually supplies - no other code needs to change.
Each list is shown to the customer as tappable options (web chat) / numbered options (WhatsApp).
The customer can always pick "Other" and type their own value. Restart the app after editing.
"""

# ---- Grade (per product; "default" is used when a product is not listed) ----
GRADES = {
    "default":                    ["YST 210", "YST 240", "YST 310", "Fe 410"],
    "MS ERW Pipe":                ["YST 210", "YST 240", "YST 310", "Fe 410", "API 5L Gr.B"],
    "MS Round Pipe":              ["YST 210", "YST 240", "YST 310", "Fe 410", "API 5L Gr.B"],
    "MS Square Hollow Section":   ["YST 210", "YST 240", "YST 310", "YST 355"],
    "MS Rectangle Hollow Section": ["YST 210", "YST 240", "YST 310", "YST 355"],
    "GI Round Pipe":              ["Light (A Class)", "Medium (B Class)", "Heavy (C Class)"],
    "GI Square Hollow Section":   ["YST 210"],
    "GI Rectangle Hollow Section": ["YST 210"],
    "GP Round Pipe":              ["YST 210", "YST 240"],
    "GP Square Hollow Section":   ["YST 210"],
    "GP Rectangle Hollow Section": ["YST 210"],
    "Large Diameter Round Pipe":  ["FE 330", "FE 410"],
    "GI ERW Pipe":                ["Light (A Class)", "Medium (B Class)", "Heavy (C Class)"],
    "Square Hollow Section":      ["YST 210", "YST 240", "YST 310", "YST 355"],
    "Rectangular Hollow Section": ["YST 210", "YST 240", "YST 310", "YST 355"],
    "Large Dia Pipes":        ["Fe 330", "Fe 410", "Fe 450", "API 5L Gr.B", "API 5L X52"],
    "Spiral Welded Pipes":        ["Gr.B"],
    "Seamless Pipe":              ["Gr.B"],
}

# ---- Standard (per product) ----
STANDARDS = {
    "default":                    ["IS 1239 (Part 1)", "IS 3589", "IS 1161", "API 5L"],
    "MS ERW Pipe":                ["IS 1239 (Part 1)", "IS 3589", "IS 1161", "API 5L", "ASTM A53"],
    "MS Round Pipe":              ["IS 1239 (Part 1)", "IS 3589", "IS 1161", "API 5L", "ASTM A53"],
    "MS Square Hollow Section":   ["IS 4923"],
    "MS Rectangle Hollow Section": ["IS 4923"],
    "GI Round Pipe":              ["IS 1239"],
    "GI Square Hollow Section":   ["IS 4923"],
    "GI Rectangle Hollow Section": ["IS 4923"],
    "GP Round Pipe":              ["IS 3601", "IS 1161", "IS 9295"],
    "GP Square Hollow Section":   ["IS 4923"],
    "GP Rectangle Hollow Section": ["IS 4923"],
    "Large Diameter Round Pipe":  ["IS 3589"],
    "GI ERW Pipe":                ["IS 1239 (Part 1)", "IS 4736 (Galvanizing)", "ASTM A53"],
    "Square Hollow Section":      ["IS 4923", "IS 1161", "EN 10219", "ASTM A500"],
    "Rectangular Hollow Section": ["IS 4923", "IS 1161", "EN 10219", "ASTM A500"],
    "Large Dia Pipes":        ["IS 3589", "API 5L", "ASTM A53"],
    "Spiral Welded Pipes":        ["ASTM A53", "API 5L"],
    "Seamless Pipe":              ["ASTM A53", "API 5L"],
}

# ---- Standard & Grade together (ONE dropdown in the Enquiry form) ----
# Each entry is (Standard, Grade).  Shown to the customer as  "IS 1161 - YST 240".  Use None for a standard that has no grade.
# EDIT these pairs to match what Shreeji actually supplies.  Restart the app after editing.
_MS  = [("IS 1239 (Part 1)", "YST 240"), ("IS 1161", "YST 210"), ("IS 1161", "YST 240"), ("IS 1161", "YST 310"),
        ("IS 3589", "Fe 330"), ("IS 3589", "Fe 410"), ("API 5L", "Gr.B"), ("ASTM A53", "Gr.B")]
_HOL = [("IS 4923", "YST 210"), ("IS 4923", "YST 240"), ("IS 4923", "YST 310"), ("IS 4923", "YST 355"),
        ("IS 1161", "YST 240"), ("IS 1161", "YST 310"), ("EN 10219", None), ("ASTM A500", None)]
_LRG = [("IS 3589", "Fe 330"), ("IS 3589", "Fe 410"), ("IS 3589", "Fe 450"), ("API 5L", "Gr.B"), ("API 5L", "X52"), ("ASTM A53", None)]
STD_GRADE = {
    "default":                    _MS,
    "MS ERW Pipe":                _MS,
    "MS Round Pipe":              [("IS 1239", None)],      # MS ERW Pipe > MS Round Pipe: standard shown to the customer
    "MS Square Hollow Section":   [("IS 4923", "YST 210"), ("IS 4923", "YST 240"), ("IS 4923", "YST 310"), ("IS 4923", "YST 355")],      # MS ERW Pipe > MS Square Hollow Section
    "MS Rectangle Hollow Section": [("IS 4923", "YST 210"), ("IS 4923", "YST 240"), ("IS 4923", "YST 310"), ("IS 4923", "YST 355")],      # MS ERW Pipe > MS Rectangle Hollow Section
    "GI Round Pipe":              [("IS 1239", None)],      # GI ERW Pipe > GI Round Pipe
    "GI Square Hollow Section":   [("IS 4923", "YST 210")],      # GI ERW Pipe > GI Square Hollow Section
    "GI Rectangle Hollow Section": [("IS 4923", "YST 210")],      # GI ERW Pipe > GI Rectangle Hollow Section
    "GP Round Pipe":              [("IS 3601", "YST 210"), ("IS 3601", "YST 240"), ("IS 1161", "YST 210"), ("IS 1161", "YST 240"), ("IS 9295", None)],
    "GP Square Hollow Section":   [("IS 4923", "YST 210")],      # GP Pipe > GP Square Hollow Section
    "GP Rectangle Hollow Section": [("IS 4923", "YST 210")],      # GP Pipe > GP Rectangle Hollow Section
    "Large Diameter Round Pipe":  [("IS 3589", "FE 330"), ("IS 3589", "FE 410")],      # Large Dia Pipes > Large Diameter Round Pipe
    "GI ERW Pipe":                [("IS 1239 (Part 1)", "Light (A Class)"), ("IS 1239 (Part 1)", "Medium (B Class)"),
                                   ("IS 1239 (Part 1)", "Heavy (C Class)"), ("IS 4736 (Galvanizing)", None), ("ASTM A53", None)],
    "Square Hollow Section":      _HOL,
    "Rectangular Hollow Section": _HOL,
    "Large Dia Pipes":        _LRG,
    "Spiral Welded Pipes":        [("IS 3589", None)],      # Spiral Welded Pipes: only IS 3589
    "Seamless Pipe":              [("ASTM A53", None), ("API 5L", "Gr.B")],      # Seamless Pipe: standard & grade shown to the customer
}

def std_grade_text(std, grade):
    """('IS 1161', 'YST 240') -> 'IS 1161 - YST 240'"""
    return f"{std} - {grade}" if grade else std

# text lists used by the web form + WhatsApp flow (product -> ["IS 1161 - YST 240", ...])
STD_GRADE_LISTS = {k: [std_grade_text(s, g) for s, g in v] for k, v in STD_GRADE.items()}

def split_std_grade(text):
    """'IS 1161 - YST 240' -> ('IS 1161', 'YST 240').  Anything the customer typed themselves -> (text, '-')."""
    t = (text or "").strip()
    for v in STD_GRADE.values():
        for s, g in v:
            if t == std_grade_text(s, g): return s, (g or "-")
    return (t or "-"), "-"

# ---- Brand preference (same for all products) ----
BRANDS = ["Shreeji", "No preference (any brand)"]

# ---- Brand preference per product (product -> brands).  When the customer picks one of these products, ONLY these brands are offered;
#      every other product uses the BRANDS list above.  "Other" is added automatically by the enquiry form. ----
_MS_BRANDS = ["Tata Pipe", "Jindal Star", "Maharashtra Seamless", "Hitech", "JTL", "Asian", "SRJ", "Semicoil"]
_MS_HOLLOW_BRANDS = ["Tata Structura", "Jindal Panther", "Hitech", "SRJ", "Semicoil"]
BRANDS_BY_PRODUCT = {
    "MS Round Pipe":            _MS_BRANDS,      # MS ERW Pipe > MS Round Pipe
    "MS Square Hollow Section":      _MS_HOLLOW_BRANDS,      # MS ERW Pipe > MS Square Hollow Section
    "MS Rectangle Hollow Section": _MS_HOLLOW_BRANDS,      # MS ERW Pipe > MS Rectangle Hollow Section
    "GI Round Pipe":                ["Jindal Star", "Hitech"],      # GI ERW Pipe > GI Round Pipe
    "GI Square Hollow Section":     ["Hitech"],      # GI ERW Pipe > GI Square Hollow Section
    "GI Rectangle Hollow Section":  ["Hitech"],      # GI ERW Pipe > GI Rectangle Hollow Section
    "GP Square Hollow Section":     ["Hitech"],      # GP Pipe > GP Square Hollow Section
    "GP Rectangle Hollow Section":  ["Hitech"],      # GP Pipe > GP Rectangle Hollow Section
    "Large Diameter Round Pipe":    ["Jindal Star", "MSL", "Tata Pipes", "Asian", "JTL", "Hitech"],      # Large Dia Pipes > Large Diameter Round Pipe
    "Spiral Welded Pipes":          ["Narmada", "Hitech"],      # Spiral Welded Pipes
    "Seamless Pipe":                ["Maharashtra Seamless Limited"],      # Seamless Pipe
}

# ---- Delivery location: "Same as my location" is added automatically from the customer's profile ----
LOCATION_EXTRA = ["Self pickup (Godown)"]

# ---- Delivery date choices: (button text, days from today, note stored with the date) ----
DATE_CHOICES = [("Urgent - within 3 days", 3, "Urgent"),
                ("Within 1 week", 7, "within 1 week"),
                ("Within 15 days", 15, "within 15 days"),
                ("Within 1 month", 30, "within 1 month")]

# ---- Small "e.g." hints shown under the free-text questions ----
EXAMPLES = {
    "size": {"default": "e.g. 50 NB  or  60.3 mm OD",
             "Square Hollow Section": "e.g. 40 x 40 mm",
             "MS Square Hollow Section": "e.g. 40 x 40 mm",
             "MS Rectangle Hollow Section": "e.g. 60 x 40 mm",
             "GI Square Hollow Section": "e.g. 40 x 40 mm", "GP Square Hollow Section": "e.g. 40 x 40 mm",
             "GI Rectangle Hollow Section": "e.g. 60 x 40 mm", "GP Rectangle Hollow Section": "e.g. 60 x 40 mm",
             "Large Diameter Round Pipe": "e.g. 400 NB  or  508 mm OD",
             "Rectangular Hollow Section": "e.g. 60 x 40 mm",
             "Large Dia Pipes": "e.g. 400 NB  or  508 mm OD",
             "Spiral Welded Pipes": "e.g. 1000 mm OD"},
    "thickness": {"default": "e.g. 3.2 mm  or  Sch 40"},
    "length":    {"default": "e.g. 6 m  /  12 m  /  Random  /  Cut length"},
    "qty":       {"default": "e.g. 5 MT  /  500 pcs  /  1000 mtr"},
}

# ---- Company introduction shown when the customer says Hi (images + video) ----
# Images/video are generated by  python tools/make_intro_media.py  (edit the text there, run again).
# You can also use your own files in /static or full https:// links (e.g. real factory photos, a YouTube link for the video).
INTRO_IMAGES = [("/static/intro/s1.png", "Shreeji SteelTubes Pvt Ltd – House of Quality Steel Tubes"),
                ("/static/intro/s2.png", "About Us – ISO 9001:2015 certified distributor, stockist & supplier"),
                ("/static/intro/s3.png", "Our Range – ERW pipes, hollow sections, seamless & spiral welded pipes"),
                ("/static/intro/s4.png", "Ready Stock – 50,000 sq. ft. at Kalamboli, supply across India"),
                ("/static/intro/s5.png", "Authorised Distributor of leading pipe brands"),
                ("/static/intro/s6.png", "Industries We Serve"),
                ("/static/intro/s7.png", "Our Journey – since 1970"),
                ("/static/intro/s8.png", "Explore our website – catalogue, certificates, quality assurance & more"),
                ("/static/intro/s9.png", "Visit Us – Head Office (Kandivali West) & Kalamboli Stock Yard"),
                ("/static/intro/s10.png", "Connect with us – website, Facebook, email & phone")]
WA_IMAGE_COUNT = 6                          # WhatsApp sends only the first N images (each is a separate message); web chat shows all
INTRO_VIDEO = "/static/intro/intro.mp4"      # "" = no video; shown only if the file exists

# ---- "Visit Us" ad card shown right after the company introduction (map + call buttons) ----
# EDIT: put the full postal address.  Map link is built from it automatically; for an exact pin paste the
# "Share" link from Google Maps into MAPS_LINK.   Restart the app after editing.
COMPANY_ADDRESS = ("*Head Office:* Office 314/315, Hive 67, 3rd Floor, Poisar Gymkhana Road, Near Raghuleela Mall, Kandivali West, Mumbai 400067\n"
                   "*Kalamboli Stock Yard:* Khedupada, Near New Taloja Bridge, Near Steel Chamber Kanta 2, Kalamboli, Raigad 410218")
COMPANY_MAP_QUERY = "Shreeji SteelTubes Pvt Ltd, Hive 67, Poisar Gymkhana Road, Kandivali West, Mumbai 400067"   # used for the auto Google Maps link
MAPS_LINK = ""                                  # e.g. "https://maps.app.goo.gl/xxxxxxxx"  ("" = auto Google Maps search of the address)
# Department-wise numbers, each gets its own Call button: [("Sales", "9999999999", "Rahul"), ("Accounts", "8888888888"), ...]
# (person name is optional). Leave [] to use ALL numbers saved in Admin -> Contacts (one per department).
COMPANY_PHONES = []

# ---- New-user information steps (About Us -> Type of Pipe -> Godown Image -> Brands -> Layers) ----
# "images" = numbers (1-10) of the pictures in INTRO_IMAGES above; "video" = also show the intro video.
# EDIT the texts freely. Restart the app after editing.
FLOW_INFO = [
    {"key": "about",  "title": "About Us",
     "text": "*Shreeji SteelTubes Pvt Ltd* – House of Quality Steel Tubes\nISO 9001:2015 certified distributor, stockist & supplier of steel pipes.\nServing customers across India since 1970.",
     "images": [1, 2, 7], "video": True},
    {"key": "pipe",   "title": "Type of Pipe",
     "text": "*Our Range*\nERW pipes, hollow sections, seamless & spiral welded pipes:",
     "images": [3], "list": "PRODUCTS"},
    {"key": "godown", "title": "Godown Image",
     "text": "*Our Godown*\nReady stock – 50,000 sq. ft. at Kalamboli, supply across India.",
     "images": [4]},
    {"key": "brands", "title": "Brands",
     "text": "*Brands*\nAuthorised distributor of leading pipe brands:",
     "images": [5], "list": "BRANDS"},
    {"key": "layers", "title": "Layers",
     "text": "*Layers*\nLayer-wise details of our pipes (as per your requirement) are shared by our team along with your quotation.",
     "images": []},                      # <- replace this text with your own Layers information
]

# ---- Representative roles asked in the Customer Details form: (key, label) ----
REPRESENTATIVES = [("sales", "Sales Representative"), ("management", "Management Representative"), ("billing", "Billing Representative"),
                   ("tc", "TC Representative"), ("accountant", "Accountant Representative"), ("director", "Director")]


# =====================================================================================
#  NEW FLOW (as per flowchart): Hi -> Home -> Existing/New user -> About -> Products -> Resource
#  -> Supply chain -> Services -> Job Application -> Enquiry Form -> Contact us.   EDIT TEXTS HERE.
# =====================================================================================
H = "/static/home/"
ABOUT_TEXT = ("*About Us*\n_We are committed to provide smooth & superior quality supply to all our customers!_\n\n"
              "M/s. Shreeji SteelTubes Pvt Ltd (ISO 9001:2015) is a leading Distributor, Stockist and Supplier of premium Iron & Steel products, based in Mumbai. "
              "We are proud to be recognised as the *House of Quality Steel Tubes*, offering a comprehensive range of high-quality steel solutions under one roof.\n\n"
              "*Our Product Range*\n- GI Pipe, MS Pipe, GP Pipe\n- Structural Hollow Sections - Circular (CHS), Square (SHS) & Rectangular (RHS) - MS YST210 / YST310 / YST355 & GI both\n"
              "- Seamless Pipes\n- Spiral Welded Pipes (H-Saw) & L-Saw Pipe\n- MS Structure, MS Plate, MS Sheet, Colour Coated Profile Sheet & Galvanised Sheet\n\n"
              "With an expansive *94,000 sq. ft.* storage facility at Kalamboli, Maharashtra's premier steel hub, we fulfil large-scale orders efficiently across Mumbai, Maharashtra and all major regions of India.\n\n"
              "*Trusted Partnerships*\nAuthorised distributors of Jindal Pipes Ltd., Maharashtra Seamless Ltd., Tata Steel Ltd., Hitech Pipes Ltd., Hitech Saw Pvt Ltd., Jindal Steel & Power Ltd., "
              "Narmada Tubes Pvt Ltd., Asian Mills Pvt Ltd., Asian Tubes Pvt Ltd., Rama Pipes Ltd., Khanna Industrial Pipes Pvt. Ltd.\n"
              "We also collaborate with Surya Prakash Pipes, Goel Pipes and JCO Gas Line Ltd. for specific customer needs.\n\n"
              "_Your One-Stop Destination for Quality Steel Tubes!_")
ABOUT_HISTORY = ("*Our History*\nOur journey began in 1970 when Mr. Navnit P. Modi and his brother-partner Mr. Rohit P. Modi started as procurement consultants & agents for steel tubes in Mumbai, "
                 "under the firm name *MODI BROTHERS* - with the goal of meeting customer needs through best quality service and professional ethics.\n\n"
                 "Under the guidance of Shri Rohit P. Modi, his son Mr. Ronak Modi started *M/s Shreeji Steel Tubes* in September 2011 as a Stockist & Supplier of steel tubes. "
                 "In the next 10 years, his hard work, long-term vision and innovative approach grew the company beyond expectation and earned it the reputation of *House of Quality Steel Tubes*.\n\n"
                 "The management has invested in a huge steel inventory and built a highly result-oriented team that can offer challenging project solutions. Strong corporate governance, "
                 "ethical practices, integrity and transparent business practices have contributed to the company's growth.")
ABOUT_VISION = ("*Vision*\nBuild for durability - we want to deliver something worthwhile that will endure the test of time, by relentlessly focusing on our customers' needs, "
                "building high-quality systems to serve them better, and planning for long-term scale with a very skilled work force.\n\n"
                "*Mission*\nTo meet the needs of the developing Indian economy with high quality steel tubes and the best quality service to customers at a competitive price.\n\n"
                "*Core Values*\nNot to do business of ethics but to do business *with* ethics. We hold ourselves to the highest standard of business ethics, integrity and fiscal responsibility.")
ABOUT_MGMT = ("*Management*\n\n*Mr. Ronak Rohit Modi* - Managing Partner\nA young & dynamic entrepreneur who plays a role similar to CEO. Strategic planning, purchase & sales policies, "
              "communication, financial & tax management, office and employee management are his key areas.\n\n"
              "*Mr. Rohit Prabhudas Modi* - Managing Partner\nWith 40 years of market knowledge and experience, he helps in all crucial functions: stock & employee management of warehouses, "
              "customer grievances, pricing policies and employee welfare.")
ABOUT_IMAGES = [(H + "cover.jpg", "House of Quality Steel Tubes"), (H + "about.jpg", "Serving Oil & Gas, Infrastructure, Power & Fabrication"),
                (H + "chrono.jpg", "Since 1970 - 80,000 sq. ft. stock yard at Kalamboli")]

# key: (menu label, image, table title, [rows], description, enquiry product)
PRODUCT_INFO = {
 "gi": ("GI Pipe", "gi.jpg", "GI Pipe - Hot Dipped Galvanized",
   [("Size", "15 NB - 500 NB (21.70 - 508.00 mm OD)"), ("Thickness", "2.00 - 12.70 mm (Light / Medium / Heavy)"), ("Length", "4.00 - 12.00 m"),
    ("Standards", "IS 1239 (Part 1) / IS 3589 Fe330-Fe410, IS 1161 / IS 3601, ASTM A53, BS 1387")],
   "Steel pipes zinc-coated by hot-dip process. Used for water supply, agriculture & irrigation, construction, fencing, firefighting lines, oil, gas & electrical conduits.", "GI Round Pipe"),
 "ms": ("MS Pipe", "ms.jpg", "MS Pipe - Black / ERW",
   [("Size", "15 NB - 600 NB (21.70 - 610.00 mm OD)"), ("Thickness", "1.00 - 16.00 mm"), ("Length", "4.00 - 12.00 m"),
    ("Grade", "IS1239, IS3589 Fe330-Fe410, IS1161 YST210-YST355, IS3601, IS9295")],
   "Strong, durable mild steel pipes for water, gas & fuel transport, structural, fire protection, conveyors, fencing, electric poles and fabrication.", "MS Round Pipe"),
 "msblack": ("MS Black Pipe", "ms.jpg", "MS Black Pipe (ERW)",
   [("Size", "21.70 - 610.00 mm OD"), ("Class", "Light / Medium / Heavy"), ("Thickness", "1.00 - 16.00 mm"), ("Length", "4.00 - 12.00 m")],
   "Uncoated black ERW pipe - superior strength, uniform design, usable indoors and outdoors; economical in operation.", "MS Round Pipe"),
 "ldp": ("Large Diameter Pipe", "ldp.jpg", "Large Diameter Pipes (ERW / H-SAW / L-SAW)",
   [("ERW", "168.30 - 610.00 mm OD, 4 - 16 mm, 4 - 12 m"), ("H-SAW / L-SAW", "457 - 3048 mm OD, 5 - 16 mm, 6 - 12 m"),
    ("Standards", "IS3589 Fe330/Fe410, API 5L up to X80, ASTM A252 / A139, IS 5504"), ("Coatings", "3LPE, Fusion Bond Epoxy, Coal Tar, Cement Mortar Lining")],
   "Used for water mains, industrial water lines, agriculture & irrigation, oil & gas pipelines, refinery piping and cross-country pipelines.", "Large Diameter Round Pipe"),
 "hollow": ("Structural Hollow Sections", "hollow.jpg", "Hollow Sections - SHS / RHS / CHS",
   [("CHS", "21.70 - 610.00 mm OD, 1.20 - 16.00 mm (IS1161 / IS3589)"), ("SHS", "12x12 - 600x600 mm, 1.20 - 25.00 mm (IS4923)"),
    ("RHS", "26x13 - 600x550 mm, 1.20 - 25.00 mm (IS4923)"), ("Grade", "YST210 / YST240 / YST310 / YST355  (high grade in ready stock)"), ("Length", "4.00 - 12.00 m")],
   "For machinery, transmission towers, automotive, construction, furniture, solar structures & electric poles. YST310 / YST355: yield 355 MPa, up to 40% steel saving. Hot-dip galvanized also available.", "MS Square Hollow Section"),
 "seamless": ("Seamless Pipe", "seamless.jpg", "Carbon Seamless Pipes",
   [("Size", "21.70 - 610 mm OD"), ("Thickness", "SCH 20 / 30 / STD / 40 / XS / 60 / 80 / 100 / 120 / 140 / 160 / XXS"), ("Grade", "ASTM A106 Gr.B / ASTM A53 (others on request)"), ("Length", "5.00 - 7.00 m")],
   "No weld seam - uniform strength & better pressure capacity. For oil & gas, petrochemical, boilers & heat exchangers, fertilizer, automotive and bearings.", "Seamless Pipe"),
 "gp": ("GP Pipe", "gp.jpg", "Pre-Galvanized Tube (GP Pipe)",
   [("Round (CHS)", "21.30 - 76.30 mm OD, IS 3601"), ("SHS", "15x15 - 100x100 mm, IS 4923"), ("RHS", "40x20 - 100x50 mm, IS 4923"),
    ("Thickness / Length", "0.80 - 3.00 mm, 4 - 6 m"), ("Zinc coating", "60 / 90 / 120 GSM")],
   "Made from zinc pre-coated sheets. For gates & grills, electrical conduits, hoardings, scaffolding, fence framework, cabling & ducting, bus bodies, greenhouses.", "GP Square Hollow Section"),
}
QA_TEXT = ("*Quality Assurance*\nWe continuously update and train ourselves to give the best solutions. Every product is thoroughly checked & inspected before dispatch.\n\n"
           "- Test certificate for all products\n- Third-party inspection & lab testing facility\n- We regularly monitor statutory, regulatory, health, safety & environmental requirements\n"
           "- We are against mixing Patra / semi-coil pipe with coil pipe")
GALLERY_IMAGES = [(H + "services.jpg", "Services - cutting, bevelling, coating, testing"), (H + "awards.jpg", "Awards & Certifications"),
                  (H + "industries.jpg", "Industries we serve"), (H + "ldp.jpg", "Large diameter pipes in stock"), (H + "hollow.jpg", "Hollow sections")]
DEALERS_TEXT = ("*Authorised Dealers & Distributors*\nAuthorised distributor of:\n- Tata Structura & Tata Pipes\n- Maharashtra Seamless Limited\n- Jindal Star & Jindal Panther (Hollow Section)\n"
                "- Hi-Tech Pipes (Hi-Tech SAW)\n- Narmada, Rama Steel Tubes, KP, Asian, Asian Mills, Asian Tubes & Pipes, Uttam\n"
                "Also associated with: JCO Gas Pipe, Tata Structura, Prakash Surya")
CLIENTS_TEXT = ("*Our Clients*\n1,500+ satisfied clients and 1,200+ active customers across India in:\n- Infrastructure & Oil & Gas\n- Prefabricated Engineered Buildings\n- Fire Fighting & HVAC\n"
                "- Automotive, Solar / Renewable & Power Plants\n- Heavy Engineering, Agriculture & General Fabrication\n\n_(Add client names / logos here in options.py -> CLIENTS_TEXT)_")
SERVICES_TEXT = ("*Services - A to Z, 365 days*\n- Cut to length, angle cut, cold saw & gas cutting\n- Bevelling, deburring, threading / socket\n- Profiling & nesting of pipe, lathe tube cutting\n"
                 "- Protective coating, special packing\n- Test certificate, lab testing & third-party inspection\n- Transportation & logistics, same-day pickup / delivery on demand\n"
                 "- Direct delivery from nearby manufacturers to save freight\n- Project & inventory management system\n_(Chamfering, tube bending & laser cutting are not in-house)_")
JOB_POSITIONS = ["Sales Executive", "Accountant / Billing", "Store / Warehouse", "Logistics / Dispatch", "Quality / QC", "Other"]
