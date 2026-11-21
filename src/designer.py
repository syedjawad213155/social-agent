"""AI Art Director: Gemini design likhta hai (HTML/CSS/SVG) -> Playwright render ->
Gemini critic screenshot dekh kar score/issues deta hai -> behtar version. Fail ho to template fallback."""
import json
import os
import re
from pathlib import Path

from google.genai import types
from playwright.sync_api import sync_playwright

from . import ai, config, design

W, H = 1080, 1350
MAX_ROUNDS = int(os.getenv("DESIGN_ROUNDS") or "2")
PASS_SCORE = 8
DESIGN_MODEL = os.getenv("DESIGN_MODEL") or config.GEMINI_MODEL
ALLOWED_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")

SYSTEM = f"""You are an award-winning senior graphic designer and front-end developer at a top branding agency.
You design social media graphics as ONE self-contained HTML file, rendered as a {W}x{H}px image.

HARD RULES
- Output a complete HTML document only (inside one ```html block). No explanation.
- body is exactly {W}x{H}px, margin 0, overflow hidden, position relative. Everything stays inside.
- No JavaScript. No external images. Only Google Fonts via <link> (allowed: Montserrat, Poppins, Inter, Playfair Display,
  DM Serif Display, Bebas Neue, Anton, Oswald, Archivo Black, Space Grotesk, Caveat, Kaushan Script, Lora).
- Icons, shapes, illustrations: inline SVG you draw yourself (clean, geometric, brand colors). Keep them simple and crisp.
- Use EXACTLY the supplied copy. Do not invent extra headlines, claims, numbers or phone numbers. You may show the brand name,
  handle, contact line and slide number if supplied.
- A CSS variable --bg-image is predefined on :root (an image url or 'none'). You may use it as a background-image
  (with a color overlay for legibility) or ignore it.
- Safe margin 72px on all sides for text. Minimum body text 34px. Strong hierarchy: one dominant element, one secondary, one small.
- Contrast: text must be clearly readable against its background (WCAG AA or better). Never place text over busy areas without a scrim.
- Premium look: generous whitespace, consistent alignment grid, limited palette (brand colors + neutrals), subtle depth
  (soft shadows, gradients, textures via CSS/SVG), no clip-art feel, no more than 2 font families.
- Fit long text with sensible font sizes; never let text overflow or clip.
"""


def _client():
    return ai.client()


def _text(prompt, image=None, json_mode=False, temperature=0.7):
    parts = []
    if image:
        parts.append(types.Part.from_bytes(data=image, mime_type="image/jpeg"))
    parts.append(prompt)

    def call():
        cfg = types.GenerateContentConfig(
            system_instruction=None if json_mode else SYSTEM, temperature=temperature,
            response_mime_type="application/json" if json_mode else None)
        return _client().models.generate_content(model=DESIGN_MODEL, contents=parts, config=cfg).text

    return ai._retry(call)


def extract_html(text):
    m = re.search(r"```html\s*(.*?)```", text, re.S) or re.search(r"(<!DOCTYPE.*</html>)", text, re.S | re.I)
    html = (m.group(1) if m else text).strip()
    if "<html" not in html.lower():
        raise ValueError("HTML nahi mila")
    return re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)


def inject_bg(html, bg_uri):
    val = f'url("{bg_uri}")' if bg_uri else "none"
    style = f"<style>:root{{--bg-image:{val};}}</style>"
    return html.replace("</head>", style + "</head>", 1) if "</head>" in html else style + html


CHECK_JS = f"""() => {{
  const out = [], W = {W}, H = {H}, M = 40;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {{
    const txt = n.textContent.trim();
    if (!txt) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.left < M || r.right > W - M || r.top < M || r.bottom > H - M)
      out.push('text "' + txt.slice(0, 28) + '" is outside the safe area or clipped');
  }}
  document.querySelectorAll('body *').forEach(el => {{
    if (el.scrollWidth > el.clientWidth + 3 && getComputedStyle(el).overflow === 'hidden' && el.tagName !== 'BODY')
      out.push(el.tagName + ' content is cut off by overflow:hidden');
  }});
  if (document.documentElement.scrollHeight > H + 2) out.push('page is taller than canvas');
  return out.slice(0, 8);
}}"""


def render_html(html):
    """-> (jpeg bytes, overflow list). Sirf fonts aur data: URLs allowed."""
    def guard(route):
        u = route.request.url
        if u.startswith(("data:", "about:")) or any(h in u for h in ALLOWED_HOSTS):
            route.continue_()
        else:
            route.abort()

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H})
        page.route("**/*", guard)
        page.set_content(html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(500)
        issues = page.evaluate(CHECK_JS)
        img = page.screenshot(type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()
    return img, issues


def critic(img, brief, overflow):
    prompt = f"""You are a ruthless art director reviewing a {W}x{H} social media graphic for a professional agency.
Brief: {brief}
Automatic checks found: {overflow or 'nothing'}.
Judge: legibility & contrast, visual hierarchy, alignment & spacing, clipped/overlapping elements, brand consistency,
follows the brief, overall polish (would a client pay for this?).
Reply JSON: {{"score": 1-10 integer, "issues": ["..."], "fix_instructions": "specific CSS/layout changes"}}"""
    d = json.loads(re.sub(r"^```(?:json)?|```$", "", _text(prompt, image=img, json_mode=True, temperature=0.2).strip()).strip())
    return int(d.get("score", 5)), d.get("issues", []), d.get("fix_instructions", "")


def _brief(brand, post, slide, role, idx, n, ref_html):
    tokens = (f"Brand: {brand.get('brand_name')} | handle: {brand.get('handle')} | contact: {brand.get('contact')}\n"
              f"Colors: primary {brand.get('primary_color')}, accent {brand.get('secondary_color')}, text {brand.get('text_color')}\n"
              f"Fonts: heading {brand.get('font_heading')}, body {brand.get('font_body')}\n"
              f"Tone: {brand.get('tone')}\nStyle reference from client: {brand.get('design_style', '')}\n"
              f"Logo url: {brand.get('logo_url') or 'none (use brand name as wordmark)'}")
    base = (f"{tokens}\n\nPost topic: {post.get('Topic')}\nClient art-direction brief (follow closely): {post.get('ImageIdea')}\n"
            f"Slide {idx + 1} of {n} (role: {role}).\nExact copy to use -> title: {slide.get('title')}\nbody: {slide.get('body', '')}\n"
            f"Button/CTA text (cover/cta only): {brand.get('cta_button')}")
    if ref_html:
        base += ("\n\nThis slide MUST share the exact same design system (colors, fonts, grid, decorations, footer) as the "
                 "cover below, only the content changes:\n" + ref_html[:6000])
    return base


def design_slide(brand, post, slide, role, idx, n, bg_uri, ref_html=None, use_critic=True):
    brief = _brief(brand, post, slide, role, idx, n, ref_html)
    html = extract_html(_text("Design this graphic.\n\n" + brief))
    best = None
    for rnd in range(MAX_ROUNDS + 1):
        img, overflow = render_html(inject_bg(html, bg_uri))
        if use_critic:
            score, issues, fix = critic(img, brief, overflow)
        else:
            score, issues, fix = (4 if overflow else 8), overflow, "Fix: " + "; ".join(overflow)
        score -= 1 if overflow else 0
        print(f"  slide {idx + 1} round {rnd}: score {score}")
        if best is None or score > best[0]:
            best = (score, img, html)
        if score >= PASS_SCORE or rnd == MAX_ROUNDS:
            break
        html = extract_html(_text(
            f"Improve this design. Problems: {issues}\nInstructions: {fix}\nAutomatic overflow report: {overflow}\n"
            f"Keep what works. Return the full corrected HTML.\n\nBRIEF:\n{brief}\n\nCURRENT HTML:\n{html}"))
    if best[0] < 5:
        raise RuntimeError("design score bohat kam")
    return best[1], best[2]


def make_slides(brand, post, copy, out_dir, stem, day_index):
    """copy: headline/subtext/image_prompt/(slides). -> list of image paths."""
    slides = copy.get("slides") or [{"title": copy["headline"], "body": copy["subtext"]}]
    n = len(slides)
    use_bg = (brand.get("use_ai_background", "no").lower() in ("yes", "1", "true"))
    bg_uri = design._bg_data_uri(copy.get("image_prompt"), day_index) if use_bg else None
    mode_ai = brand.get("design_mode", "ai").lower() != "template"
    paths, ref = [], None
    for i, s in enumerate(slides):
        out = Path(out_dir) / (f"{stem}-s{i + 1}.jpg" if n > 1 else f"{stem}.jpg")
        role = "cover" if i == 0 else ("closing call-to-action" if i == n - 1 else "content")
        done = False
        if mode_ai:
            try:
                img, html = design_slide(brand, post, s, role, i, n, bg_uri, ref,
                                         use_critic=(i == 0))
                out.write_bytes(img)
                ref = ref or html
                done = True
            except Exception as e:
                print(f"  slide {i + 1}: AI design fail ({type(e).__name__}), template fallback")
        if not done:
            design.render(brand, s["title"], s.get("body", ""), copy.get("image_prompt", ""), out, day_index + i)
        paths.append(out)
    return paths
