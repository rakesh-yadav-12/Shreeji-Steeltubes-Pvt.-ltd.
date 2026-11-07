"""Hindi / English language switch.

How it works
------------
The bot's logic and button *tokens* ('s:about', 'p:gi' ...) never change - only the text the customer SEES is
translated, at one single place (`whatsapp._post`).  So every flow (menu, forms, enquiry, WhatsApp number-replies)
works in both languages without touching bot.py's logic.

Add / fix a translation
* EXACT   : whole-string match (buttons, form labels, placeholders).  Use for short labels.
* PHRASES : text fragment found anywhere inside a longer message (longest fragment is applied first).
* PATTERNS: regex for sentences that contain numbers / names, e.g. "Enquiry #12 submitted!".
Anything not in the tables is simply shown in English - nothing breaks.
"""
import re

LANGS = ("en", "hi")

# ---------------------------------------------------------------- whole-string translations (buttons, labels, placeholders)
EXACT = {
    # user type / main navigation
    "✅ Existing Customer": "✅ मौजूदा ग्राहक", "🆕 New Customer": "🆕 नया ग्राहक", "🆕 New User": "🆕 नया ग्राहक",
    "🏠 Main menu": "🏠 मुख्य मेन्यू", "🏠 Home": "🏠 होम",
    "ℹ️ About Us": "ℹ️ हमारे बारे में", "📦 Products": "📦 उत्पाद", "📚 Resource": "📚 संसाधन", "📚 Resources": "📚 संसाधन",
    "🚚 Supply Chain": "🚚 सप्लाई चेन", "🛠 Services": "🛠 सेवाएँ", "💼 Job Application Form": "💼 नौकरी आवेदन फ़ॉर्म", "💼 Join our Team": "💼 हमारी टीम से जुड़ें",
    "📋 Enquiry Form": "📋 पूछताछ फ़ॉर्म", "📋 Product Enquiry Form": "📋 प्रोडक्ट पूछताछ फ़ॉर्म", "📋 Customer Enquiry Form": "📋 ग्राहक पूछताछ फ़ॉर्म", "📞 Contact Us": "📞 संपर्क करें",
    "📝 Customer Details Form": "📝 ग्राहक विवरण फ़ॉर्म", "📝 New Enquiry": "📝 नई पूछताछ",
    "⬅ All sections": "⬅ सभी सेक्शन", "⬅ About Us": "⬅ हमारे बारे में", "⬅ Products": "⬅ उत्पाद", "⬅ Resource": "⬅ संसाधन",
    "⬅ Supply Chain": "⬅ सप्लाई चेन", "⬅ Back": "⬅ पीछे",
    "Next ➡": "आगे ➡", "⏭ Skip to Details Form": "⏭ सीधे फ़ॉर्म पर जाएँ", "📝 Fill Customer Details ➡": "📝 ग्राहक विवरण भरें ➡",
    "📋 Enquire this product": "📋 इस उत्पाद की पूछताछ करें",
    "📘 Product Catalogue": "📘 प्रोडक्ट कैटलॉग", "🏅 Certificates": "🏅 प्रमाणपत्र", "✅ Quality Assurance": "✅ गुणवत्ता आश्वासन",
    "🖼 Gallery": "🖼 गैलरी", "📄 Documents": "📄 दस्तावेज़",
    "🏭 Authorised Dealers & Distributors": "🏭 अधिकृत डीलर और वितरक", "💬 Request For Quote": "💬 कोटेशन का अनुरोध",
    "🤝 Vendor Registration": "🤝 वेंडर पंजीकरण", "👥 Clients": "👥 हमारे ग्राहक",
    "📜 Our History": "📜 हमारा इतिहास", "🎯 Vision, Mission & Values": "🎯 विज़न, मिशन और मूल्य", "👥 Management": "👥 प्रबंधन",
    "🗺️ Open in Google Maps": "🗺️ गूगल मैप्स में खोलें",
    # chips-hints / placeholders / list titles (lt)
    "Select user type": "ग्राहक प्रकार चुनें", "Select next step": "अगला विकल्प चुनें", "Select action": "विकल्प चुनें",
    "Select section": "सेक्शन चुनें", "Select product": "उत्पाद चुनें", "Select resource": "संसाधन चुनें", "Select document": "दस्तावेज़ चुनें",
    "Select supply chain topic": "सप्लाई चेन विषय चुनें", "Select About Us topic": "विषय चुनें",
    "Type a message…": "संदेश लिखें…", "Type a message… e.g. price, catalogue, contact": "संदेश लिखें… जैसे भाव, कैटलॉग, संपर्क",
    "Tap an option above…": "ऊपर से कोई विकल्प चुनें…", "Tap Next ➡ to continue…": "आगे बढ़ने के लिए 'आगे ➡' दबाएँ…",
    "Fill the form above…": "ऊपर का फ़ॉर्म भरें…",
    # form titles / buttons / notes
    "Save & Continue ➡": "सेव करें और आगे बढ़ें ➡", "Submit Enquiry ✅": "पूछताछ सबमिट करें ✅", "Submit Application ✅": "आवेदन सबमिट करें ✅",
    "Please fill in your details. Fields marked * are required.": "कृपया अपना विवरण भरें। * वाले खाने अनिवार्य हैं।",
    "Tell us what you need. Fields marked * are required.": "आपको क्या चाहिए, बताइए। * वाले खाने अनिवार्य हैं।",
    "Fields marked * are required.": "* वाले खाने अनिवार्य हैं।",
    "Customer Details": "ग्राहक विवरण", "Product Requirement": "उत्पाद आवश्यकता", "Application": "आवेदन",
    "Representative Details  (add at least one mobile number)": "प्रतिनिधि विवरण (कम से कम एक मोबाइल नंबर दें)",
    # form labels
    "Customer Name": "ग्राहक का नाम", "Company / Firm Name": "कंपनी / फ़र्म का नाम", "GST Number": "जीएसटी नंबर", "UC Code": "यूसी कोड",
    "Portal Access": "पोर्टल एक्सेस", "Product": "उत्पाद", "Size / NB / OD": "साइज़ / NB / OD", "Thickness / Schedule": "मोटाई / शेड्यूल",
    "Length": "लंबाई", "Quantity": "मात्रा", "Grade": "ग्रेड", "Standard": "मानक (स्टैंडर्ड)", "Brand Preference": "पसंदीदा ब्रांड",
    "Delivery Date": "डिलीवरी की तारीख", "Remarks / Special requirement": "टिप्पणी / विशेष आवश्यकता",
    "Full Name": "पूरा नाम", "Mobile No.": "मोबाइल नंबर", "Email": "ईमेल", "Position applying for": "किस पद के लिए आवेदन",
    "Qualification": "योग्यता", "Experience": "अनुभव", "Current City": "वर्तमान शहर", "About you / resume link": "अपने बारे में / रिज़्यूमे लिंक",
    "Contact Person": "संपर्क व्यक्ति",
    # placeholders
    "Full name": "पूरा नाम", "Firm name": "फ़र्म का नाम", "Your UC code (if any)": "आपका यूसी कोड (यदि हो)", "Name": "नाम",
    "10-digit mobile": "10 अंकों का मोबाइल नंबर", "Select product": "उत्पाद चुनें", "Select or type": "चुनें या लिखें", "Select brand": "ब्रांड चुनें",
    "Select position": "पद चुनें", "Anything else we should know?": "कुछ और बताना चाहें तो लिखें",
    "e.g. 50 NB or 60.3 mm OD": "जैसे 50 NB या 60.3 mm OD", "e.g. 3.2 mm or Sch 40": "जैसे 3.2 mm या Sch 40",
    "e.g. 6 m / 12 m / Random": "जैसे 6 m / 12 m / रैंडम", "Select length": "लंबाई चुनें", "Type length (e.g. 8 m / Random)": "लंबाई लिखें (जैसे 8 m / रैंडम)", "e.g. 5 MT / 500 pcs": "जैसे 5 MT / 500 पीस", "e.g. 5": "जैसे 5", "Type brand name": "ब्रांड का नाम लिखें", "Unit": "इकाई", "Select": "चुनें",
    "Your name": "आपका नाम", "City": "शहर", "Yes": "हाँ", "No": "नहीं",
    "Please fill the Customer Details Form first": "कृपया पहले ग्राहक विवरण फ़ॉर्म भरें",
}

# ---------------------------------------------------------------- fragments inside longer messages
PHRASES = [
    # "Next ➡ <section>" buttons (section name comes from bot.SECTIONS)
    ("Next ➡ About Us", "आगे ➡ हमारे बारे में"), ("Next ➡ Products", "आगे ➡ उत्पाद"), ("Next ➡ Resource", "आगे ➡ संसाधन"),
    ("Next ➡ Supply Chain", "आगे ➡ सप्लाई चेन"), ("Next ➡ Services", "आगे ➡ सेवाएँ"), ("Next ➡ Job Application Form", "आगे ➡ नौकरी आवेदन फ़ॉर्म"),
    ("Next ➡ Product Enquiry Form", "आगे ➡ प्रोडक्ट पूछताछ फ़ॉर्म"), ("Next ➡ Enquiry Form", "आगे ➡ पूछताछ फ़ॉर्म"), ("Next ➡ Contact Us", "आगे ➡ संपर्क करें"),
    ("Customer Details Form", "ग्राहक विवरण फ़ॉर्म"), ("About Us", "हमारे बारे में"), ("_0 = main menu_", "_0 = मुख्य मेन्यू_"),
    ("Welcome to *Shreeji Steeltubes Pvt Ltd* 🙏", "*श्रीजी स्टीलट्यूब्स प्रा. लि.* में आपका स्वागत है 🙏"),
    ("Welcome to *Shreeji SteelTubes Pvt. Ltd.* 🙏", "*श्रीजी स्टीलट्यूब्स प्रा. लि.* में आपका स्वागत है 🙏"),
    ("Welcome to *Shreeji SteelTubes*!", "*श्रीजी स्टीलट्यूब्स* में आपका स्वागत है!"),
    ("_House of Quality Steel Tubes_", "_गुणवत्तापूर्ण स्टील ट्यूब्स का घर_"),
    ("Type *Hi* to get started.", "शुरू करने के लिए *Hi* लिखें।"),
    ("Welcome back,", "आपका फिर से स्वागत है,"),
    ("What would you like to do?", "आप क्या करना चाहेंगे?"),
    ("*Are you an existing user?*", "*क्या आप हमारे मौजूदा ग्राहक हैं?*"),
    ("Please choose what you would like to see 👇", "कृपया चुनें कि आप क्या देखना चाहते हैं 👇"),
    ("*All sections* 👇", "*सभी सेक्शन* 👇"),
    ("*Our Products*\nChoose a product 👇", "*हमारे उत्पाद*\nकोई उत्पाद चुनें 👇"),
    ("📞 Contact page opened. Tap below to continue 👇", "📞 संपर्क पेज खुल गया है। आगे बढ़ने के लिए नीचे दबाएँ 👇"),
    ("🛠 Services opened. Tap below to continue 👇", "🛠 सेवाएँ पेज खुल गया है। आगे बढ़ने के लिए नीचे दबाएँ 👇"),
    ("📦 Products opened. Tap below to continue 👇", "📦 उत्पाद पेज खुल गया है। आगे बढ़ने के लिए नीचे दबाएँ 👇"),
    ("Tap below to see our products 👇", "हमारे उत्पाद देखने के लिए नीचे दबाएँ 👇"),
    ("*Resource*\nChoose one 👇", "*संसाधन*\nकोई एक चुनें 👇"),
    ("*Supply Chain*\nChoose one 👇", "*सप्लाई चेन*\nकोई एक चुनें 👇"),
    ("*Documents*\nTap a document to receive it 👇", "*दस्तावेज़*\nदस्तावेज़ पाने के लिए उस पर दबाएँ 👇"),
    ("ℹ️ No documents added yet. Our team will add them soon.", "ℹ️ अभी कोई दस्तावेज़ नहीं जोड़ा गया है। हमारी टीम जल्द ही जोड़ेगी।"),
    ("ℹ️ This will be shared soon.", "ℹ️ यह जल्द ही साझा किया जाएगा।"),
    ("✅ Sent! 👆", "✅ भेज दिया गया! 👆"),
    ("*Gallery*", "*गैलरी*"), ("_Swipe to see more_", "_और देखने के लिए स्वाइप करें_"),
    ("*Contact Details (Department wise)*", "*संपर्क विवरण (विभाग अनुसार)*"),
    ("📍 *Visit Us*", "📍 *हमसे मिलें*"), ("🗺️ Find us on map:", "🗺️ नक्शे पर हमें खोजें:"),
    ("👆 Tap below to continue", "👆 आगे बढ़ने के लिए नीचे दबाएँ"),
    ("Please share your details first 👇", "कृपया पहले अपना विवरण साझा करें 👇"),
    ("Please fill the form below 👇", "कृपया नीचे का फ़ॉर्म भरें 👇"),
    ("Please fill the *Enquiry Form* below 👇", "कृपया नीचे का *पूछताछ फ़ॉर्म* भरें 👇"),
    ("⚠️ Please correct the highlighted field(s) and submit again.", "⚠️ कृपया लाल रंग वाले खाने सुधारकर फिर से सबमिट करें।"),
    ("Your details are saved.", "आपका विवरण सेव हो गया है।"),
    ("Our team will call you shortly on", "हमारी टीम जल्द ही आपको कॉल करेगी:"),
    ("Our team will contact you shortly.", "हमारी टीम जल्द ही आपसे संपर्क करेगी।"),
    ("📋 *Summary*", "📋 *सारांश*"),
    ("_Send *enquiry* for a new enquiry • *menu* for the main menu._", "_नई पूछताछ के लिए *enquiry* • मुख्य मेन्यू के लिए *menu* भेजें।_"),
    ("_Reply with a number • 0 = main menu_", "_नंबर भेजकर चुनें • 0 = मुख्य मेन्यू_"),
    ("_Reply *next* to continue • *skip* = go to the form • *back*_", "_आगे बढ़ने के लिए *next* • फ़ॉर्म पर जाने के लिए *skip* • पीछे जाने के लिए *back* भेजें_"),
    ("*(required)*", "*(अनिवार्य)*"), ("_(optional)_", "_(वैकल्पिक)_"),
    ("_Type a date as DD-MM-YYYY_", "_तारीख DD-MM-YYYY में लिखें_"),
    ("_*skip* to leave blank_", "_खाली छोड़ने के लिए *skip* लिखें_"),
    ("⚠️ Please reply with a number from the list.", "⚠️ कृपया सूची में से कोई नंबर भेजें।"),
    ("_Reply with a number or type your own_", "_नंबर भेजें या अपना उत्तर लिखें_"),
    ("_Reply with a number_", "_नंबर भेजें_"),
    ("Please fill the form below", "कृपया नीचे का फ़ॉर्म भरें"),
    ("🌐 _Type *hindi* for Hindi • *english* for English_", "🌐 _हिंदी के लिए *hindi* • English के लिए *english* लिखें_"),
    ("✅ भाषा", "✅ भाषा"),
    ("🎤 You said:", "🎤 आपने कहा:"),
    ("🎤 Sorry, I could not understand your voice message. Please type your message or send *hi*.", "🎤 माफ़ कीजिए, मैं आपका वॉइस संदेश समझ नहीं पाया। कृपया लिखकर भेजें या *hi* भेजें।"),
    ("📲 A confirmation will also be sent on WhatsApp to", "📲 पुष्टि का संदेश WhatsApp पर भी भेजा जाएगा:"),
    ("\U0001F60A You are welcome! Anything else I can help you with?", "\U0001F60A आपका स्वागत है! क्या मैं और कुछ मदद कर सकता हूँ?"),
    ("\U0001F64F Thank you for visiting *Shreeji SteelTubes Pvt. Ltd.*. Have a great day! Send *hi* anytime to chat again.",
     "\U0001F64F *श्रीजी स्टीलट्यूब्स* पर आने के लिए धन्यवाद। आपका दिन शुभ हो! दोबारा बात करने के लिए कभी भी *hi* भेजें।"),
    ("\U0001F4A1 *How can I help you?*\nYou can tap the buttons, or simply type:", "\U0001F4A1 *मैं आपकी क्या मदद करूँ?*\nआप बटन दबा सकते हैं, या सीधे लिखें:"),
    ("\u2022 *products* \u2013 our pipes & tubes (GI, MS, Hollow Sections, Seamless, GP)", "\u2022 *products* \u2013 हमारे पाइप और ट्यूब (GI, MS, हॉलो सेक्शन, सीमलेस, GP)"),
    ("\u2022 *price* / *enquiry* \u2013 send your requirement", "\u2022 *price* / *enquiry* \u2013 अपनी ज़रूरत भेजें"),
    ("\u2022 *catalogue* / *documents* / *certificates* \u2013 get files", "\u2022 *catalogue* / *documents* / *certificates* \u2013 फ़ाइलें पाएँ"),
    ("\u2022 *contact* \u2013 call, email & address", "\u2022 *contact* \u2013 कॉल, ईमेल और पता"),
    ("\u2022 *menu* \u2013 back to the main menu", "\u2022 *menu* \u2013 मुख्य मेन्यू पर वापस"),
    ("\U0001F64F Sorry, I could not find that.\nPlease pick an option below, or type *products*, *price*, *catalogue*, *contact* or *help* \U0001F447",
     "\U0001F64F माफ़ कीजिए, मुझे यह नहीं मिला।\nनीचे से कोई विकल्प चुनें, या *products*, *price*, *catalogue*, *contact* या *help* लिखें \U0001F447"),
    ("⏳ You are sending messages too fast. Please wait a few seconds and try again.", "⏳ आप बहुत तेज़ी से संदेश भेज रहे हैं। कृपया कुछ सेकंड रुककर फिर कोशिश करें।"),
    ("⚠️ Connection problem. Please check your internet and try again.", "⚠️ कनेक्शन में समस्या है। कृपया इंटरनेट जाँचकर फिर कोशिश करें।"),
]

# ---------------------------------------------------------------- sentences with numbers / names
PATTERNS = [
    (r"✅ \*Enquiry #(\d+) submitted!\*", r"✅ *पूछताछ #\1 सबमिट हो गई!*"),
    (r"📋 Enquiry #(\d+) – Summary", r"📋 पूछताछ #\1 – सारांश"),
    (r"Thanks, \*([^*]+)\*\.", r"धन्यवाद, *\1*।"),
    (r"✅ Thanks, \*([^*]+)\*!", r"✅ धन्यवाद, *\1*!"),
    (r"_Saved: (.+?) – send \*ok\* to keep it_", r"_सेव है: \1 – इसे रखने के लिए *ok* भेजें_"),
]
_PATTERNS = [(re.compile(p), r) for p, r in PATTERNS]
_PHRASES = sorted(PHRASES, key=lambda x: -len(x[0]))


def tr(text, lang):
    """Translate one string into `lang` ('hi' / 'en').  Unknown text is returned unchanged."""
    if lang != "hi" or not isinstance(text, str) or not text:
        return text
    s = text.strip()
    if s in EXACT:
        return text.replace(s, EXACT[s])
    out = text
    for en, hi in _PHRASES:
        if en in out:
            out = out.replace(en, hi)
    for rx, rep in _PATTERNS:
        out = rx.sub(rep, out)
    # numbered WhatsApp menu lines "3. 📦 Products" -> translate the label part
    if "\n" in out:
        out = "\n".join(_line(x) for x in out.split("\n"))
    return out


def _line(line):
    m = re.match(r"^(\d+\.\s+)(.+)$", line)
    if m and m.group(2).strip() in EXACT:
        return m.group(1) + EXACT[m.group(2).strip()]
    m = re.match(r"^([-•]\s*)(.+)$", line)
    if m and m.group(2).strip() in EXACT:
        return m.group(1) + EXACT[m.group(2).strip()]
    return line


form_tr = lambda form, lang: _form(form, lang)
_FORM_KEYS = ("title", "submit", "note", "label", "ph", "err")


def _form(obj, lang):
    """Translate visible form texts only (never option values / saved values)."""
    if isinstance(obj, dict):
        return {k: (tr(v, lang) if k in _FORM_KEYS and isinstance(v, str) else _form(v, lang) if k in ("sections", "fields") else v)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_form(x, lang) for x in obj]
    return obj


def _chips(chips, lang):
    return [[tr(c[0], lang)] + list(c[1:]) for c in chips]


def tr_ui(ui, lang):
    """Translate the web-chat extras (chips, placeholder, list title, form, card title, links, progress)."""
    if lang != "hi" or not ui:
        return ui
    o = dict(ui)
    for k in ("chips", "extra"):
        if o.get(k):
            o[k] = _chips(o[k], lang)
    for k in ("ph", "lt"):
        if o.get(k):
            o[k] = tr(o[k], lang)
    if o.get("form"):
        o["form"] = _form(o["form"], lang)
    if o.get("card"):
        o["card"] = dict(o["card"], title=tr(o["card"].get("title", ""), lang))
    if o.get("links"):
        o["links"] = [[tr(a, lang), b] for a, b in o["links"]]
    if o.get("progress"):
        p = list(o["progress"]); p[2] = tr(p[2], lang) if len(p) > 2 else ""; o["progress"] = p
    return o


# ---------------------------------------------------------------- typed language commands (web + WhatsApp)
_HI_RX = re.compile(r"^(hindi|हिंदी|हिन्दी|hindi me|hindi mein|हिंदी में|hindi mai|lang:?hi|language hindi)$", re.I)
_EN_RX = re.compile(r"^(english|इंग्लिश|अंग्रेज़ी|अंग्रेजी|english me|english mein|lang:?en|language english)$", re.I)
_ASK_RX = re.compile(r"^(language|lang|bhasha|भाषा|change language|language change)$", re.I)


def lang_command(text):
    """Return 'hi' / 'en' / 'toggle' / 'ask' when the message is a language command, else None."""
    w = re.sub(r"[^\w\s:\u0900-\u097F]", "", (text or "").strip().lower())
    if w == "lang:toggle": return "toggle"
    if _HI_RX.match(w): return "hi"
    if _EN_RX.match(w): return "en"
    if _ASK_RX.match(w): return "ask"
    return None


# messages shown right after a switch (always in the NEW language)
SWITCHED = {"hi": "✅ भाषा *हिंदी* में बदल दी गई है।", "en": "✅ Language changed to *English*."}
ASK = "🌐 Choose your language / अपनी भाषा चुनें"
