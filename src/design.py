import base64
import html
import os
import urllib.parse
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LAYOUTS = ["L1", "L2", "L3"]


def _bg_data_uri(prompt, seed):
    """Free AI background (Pollinations). Na mile to None -> gradient design."""
    if not prompt:
        return None
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) +
           f"?width=1080&height=1350&nologo=true&seed={seed}")
    try:
        r = requests.get(url, timeout=90)
        if r.ok and r.headers.get("content-type", "").startswith("image"):
            return "data:image/jpeg;base64," + base64.b64encode(r.content).decode()
    except requests.RequestException:
        pass
    print("AI background nahi mila, gradient use ho raha hai")
    return None


def _lum(hexc):
    h = hexc.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _rgba(hexc, a):
    h = hexc.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


def _font(name, default):
    n = (name or default).strip()
    return urllib.parse.quote_plus(n), n


def render(brand, headline, subtext, image_prompt, out_path, day_index):
    tpl = (ROOT / "templates" / "post.html").read_text(encoding="utf-8")
    fh, fh_css = _font(brand.get("font_heading"), "Poppins")
    fb, fb_css = _font(brand.get("font_body"), "Inter")
    bg = _bg_data_uri(image_prompt, day_index)
    prim = brand.get("primary_color", "#0F172A")
    sec = brand.get("secondary_color", "#F59E0B")
    light_theme = _lum(brand.get("text_color", "#FFFFFF")) < 0.5   # gehra text = halka theme
    if light_theme:
        body_bg = prim                                   # saaf, solid halka background
        shade = f"background: {_rgba(prim, 0.80)};" if bg else ""
        bar = f'<div class="bar"></div>'
    else:
        body_bg = f"linear-gradient(145deg, {prim}, {sec})"
        shade = "background: linear-gradient(180deg, rgba(0,0,0,.35), rgba(0,0,0,.72));" if bg else ""
        bar = ""
    bg_css = f"background-image: url('{bg}');" if bg else ""
    n = len(headline)
    hsize = 118 if n <= 28 else 100 if n <= 50 else 82
    logo = ""
    if brand.get("logo_url"):
        logo = f'<img class="logo" src="{html.escape(brand["logo_url"])}">'
    reps = {
        "__FONT_H__": fh, "__FONT_B__": fb,
        "__FONT_H_CSS__": fh_css, "__FONT_B_CSS__": fb_css,
        "__PRIMARY__": brand.get("primary_color", "#0F172A"),
        "__SECONDARY__": brand.get("secondary_color", "#F59E0B"),
        "__TEXT__": brand.get("text_color", "#FFFFFF"),
        "__BG__": bg_css, "__BODYBG__": body_bg, "__BAR__": bar, "__SHADE__": shade, "__HSIZE__": str(hsize),
        "__LAYOUT__": LAYOUTS[day_index % 3], "__LOGO__": logo,
        "__BRAND__": html.escape(brand.get("brand_name", "")),
        "__HEADLINE__": html.escape(headline),
        "__SUBTEXT__": html.escape(subtext),
        "__HANDLE__": html.escape(brand.get("handle", "")),
        "__CTA__": html.escape(brand.get("cta_button", "Learn more")),
    }
    for k, v in reps.items():
        tpl = tpl.replace(k, v)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1080, "height": 1350})
        page.set_content(tpl, wait_until="networkidle")
        page.wait_for_timeout(700)
        page.screenshot(path=str(out_path), type="jpeg", quality=92)
        b.close()
