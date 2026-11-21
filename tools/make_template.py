from datetime import date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

F = "Arial"
head_fill = PatternFill("solid", fgColor="1F3A5F")
inp_fill = PatternFill("solid", fgColor="FFF9DB")
wb = Workbook()

def style_header(ws, widths):
    for i, w in enumerate(widths, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(name=F, bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[c.column_letter].width = w
    ws.freeze_panes = "A2"

# ---- Posts ----
ws = wb.active; ws.title = "Posts"
cols = ["Date", "Platform", "Topic", "Headline", "Subtext", "Audience", "ImageIdea", "Hold",
        "Status", "Caption", "Hashtags", "ImageURL", "PostLink", "Notes"]
ws.append(cols)
style_header(ws, [12, 11, 34, 26, 26, 24, 30, 7, 11, 50, 40, 30, 30, 30])
topics = [
    ("5 tips to choose the right product", "Shoppers 20-35", "clean flat-lay of products on a table"),
    ("Customer success story of the week", "Existing customers", "smiling customer with package"),
    ("Behind the scenes of our team", "Followers who love our story", "workshop with team at work"),
    ("Common myths about our industry", "New customers", "bold abstract shapes, bright colors"),
    ("Weekend special offer announcement", "Local buyers", "festive table with warm lights"),
    ("How to use our product in 3 steps", "First-time buyers", "hands using the product, close up"),
    ("Thank you to our community", "All followers", "warm sunrise city skyline"),
]
d0 = date(2026, 11, 22)
for i, (t, a, img) in enumerate(topics):
    r = [(d0 + timedelta(days=i)).strftime("%Y-%m-%d"), "Both", t, "", "", a, img, "", "", "", "", "", "", ""]
    ws.append(r)
for row in ws.iter_rows(min_row=2, max_row=500):
    for c in row:
        c.font = Font(name=F, size=10)
        c.alignment = Alignment(vertical="top", wrap_text=True)
    row[0].number_format = "@"
    for c in row[:8]:
        c.fill = inp_fill
dv = DataValidation(type="list", formula1='"Instagram,Facebook,Both"', allow_blank=True)
ws.add_data_validation(dv); dv.add("B2:B500")
dv2 = DataValidation(type="list", formula1='"YES"', allow_blank=True)
ws.add_data_validation(dv2); dv2.add("H2:H500")

# ---- Brand ----
b = wb.create_sheet("Brand")
b.append(["Setting", "Value", "Explanation"])
style_header(b, [24, 48, 70])
rows = [
    ("brand_name", "Demo Brand", "Brand ka naam (design mein dikhega)"),
    ("handle", "@demobrand", "Instagram/Facebook handle (design ke neeche)"),
    ("industry", "Online fashion store", "Aap ka niche"),
    ("about", "We sell affordable, quality clothing delivered across Pakistan.", "Brand ka 1-2 line taaruf"),
    ("tone", "Friendly, confident, helpful", "Lehja"),
    ("language", "Roman Urdu mixed with simple English", "Caption ki zaban (e.g. English / Urdu / Roman Urdu)"),
    ("audience_default", "Men and women 18-35 in Pakistan", "Agar post row mein Audience khali ho"),
    ("cta", "DM us to order or visit our page.", "Caption ke aakhir ka call-to-action"),
    ("cta_button", "Order now", "Design ke neeche button ka chhota text"),
    ("contact", "WhatsApp 03XX-XXXXXXX", "Replies mein diya jane wala rabta"),
    ("primary_color", "#0F172A", "Mukhya rang (hex)"),
    ("secondary_color", "#F59E0B", "Doosra rang (hex)"),
    ("text_color", "#FFFFFF", "Text ka rang (hex)"),
    ("font_heading", "Poppins", "Google Fonts ka naam"),
    ("font_body", "Inter", "Google Fonts ka naam"),
    ("logo_url", "", "Optional: logo ka public image link (khali chhor sakte hain)"),
    ("forbidden_topics", "politics, religion, competitor names, medical claims", "Jin par kabhi baat nahi karni"),
    ("escalation_keywords", "refund,legal,lawyer,court,police,scam,fraud,cheat,cancel,complaint", "Ye lafz aaye to insaan ko bheja jaye (comma se alag)"),
    ("safe_reply_dm", "Thank you for reaching out. Our team will contact you shortly.", "Mushkil DM ka mehfooz jawab"),
    ("safe_reply_comment", "Thanks for your comment! Please send us a DM and our team will help you.", "Mushkil comment ka mehfooz jawab"),
]
for r in rows:
    b.append(list(r))
for row in b.iter_rows(min_row=2):
    for c in row:
        c.font = Font(name=F, size=10); c.alignment = Alignment(vertical="top", wrap_text=True)
    row[1].fill = inp_fill

# ---- FAQ ----
q = wb.create_sheet("FAQ")
q.append(["Question", "Answer"])
style_header(q, [45, 80])
faq = [
    ("What are your delivery charges and time?", "Delivery is 3-5 working days. Charges: Rs 200 (free above Rs 5,000)."),
    ("How can I order?", "Send us a DM with the product name, size and your city. We confirm on WhatsApp."),
    ("Do you offer cash on delivery?", "Yes, cash on delivery is available in major cities."),
    ("What is your return policy?", "Unused items can be exchanged within 7 days of delivery."),
    ("What are your working hours?", "Monday to Saturday, 10am to 8pm."),
]
for r in faq:
    q.append(list(r))
for row in q.iter_rows(min_row=2, max_row=200):
    for c in row:
        c.font = Font(name=F, size=10); c.alignment = Alignment(vertical="top", wrap_text=True); c.fill = inp_fill

# ---- Guide ----
g = wb.create_sheet("READ ME", 0)
g.column_dimensions["A"].width = 110
lines = [
    "SOCIAL AGENT SHEET - kaise bharein",
    "",
    "Posts tab: peele (yellow) khaane aap bharte hain: Date, Platform, Topic, Audience, ImageIdea. Baqi agent bharta hai.",
    "Date ka format hamesha YYYY-MM-DD likhein (e.g. 2026-11-22). Pakistan time ke hisab se.",
    "Headline/Subtext khali chhor dein to agent khud likhega. Bharein to wohi use hoga.",
    "Hold mein YES likhein to us din ki post nahi jayegi.",
    "Status: Designed -> Published / Partial / Failed / Held. Dobara try karne ke liye Status khali karein.",
    "Brand tab aur FAQ tab ko apne business ke hisab se zaroor badlein (ye misali/demo data hai).",
    "Inbox_Log tab agent khud banata hai. Action = 'Needs Human' wali rows aap ko khud dekhni hain.",
]
for i, t in enumerate(lines, 1):
    c = g.cell(row=i, column=1, value=t)
    c.font = Font(name=F, size=11, bold=(i == 1)); c.alignment = Alignment(wrap_text=True)
wb.save("Social_Agent_Sheet_Template.xlsx")
print("saved")
