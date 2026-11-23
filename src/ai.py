import json
import os
import re
import time
import requests

from google import genai
from google.genai import types

from .config import GEMINI_MODEL

_client = None
_discovered_models = None

FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def list_available_models():
    models = []
    for m in client().models.list():
        name = getattr(m, "name", "")
        actions = getattr(m, "supported_actions", None) or []
        if not actions or "generateContent" in actions:
            clean = name.replace("models/", "").strip()
            if clean and all(x not in clean for x in ("embedding", "imagen", "veo", "tts", "audio")):
                models.append(clean)
    return models


def _candidate_models():
    global _discovered_models
    out, seen = [], set()
    for m in FALLBACK_MODELS:
        name = (m or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)

    if _discovered_models is None:
        try:
            _discovered_models = list_available_models()
        except Exception:
            _discovered_models = []

    for m in _discovered_models:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def client():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=15000),
        )
    return _client


def _groq_fallback(prompt, system=None, temperature=0.7, json_mode=False):
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        raise RuntimeError("Gemini quota exhausted (429) and GROQ_API_KEY is not set.")

    print("Switching to Groq fallback (llama-3.3-70b-versatile)...", flush=True)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _generate_with_fallback(prompt, config, system=None, temperature=0.7, json_mode=False):
    last_err = None
    models = _candidate_models()
    for idx, model_name in enumerate(models):
        try:
            print(f"Trying Gemini model: {model_name}", flush=True)
            r = client().models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            return r.text or ""
        except Exception as e:
            last_err = e
            err_str = str(e)
            print(f"Model {model_name} failed: {type(e).__name__}", flush=True)
            # Agar 429 ya 404 aaye to fauran agla model try karein
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "404" in err_str:
                continue
            if idx < len(models) - 1:
                time.sleep(1)

    # Agar saare Gemini models fail/429 hon to Groq fallback chalayein
    if os.getenv("GROQ_API_KEY"):
        return _groq_fallback(prompt, system=system, temperature=temperature, json_mode=json_mode)
    raise last_err


def ask_json(prompt, system=None, temperature=0.8):
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
    )
    raw = _generate_with_fallback(
        prompt, cfg, system=system, temperature=temperature, json_mode=True
    )
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text).strip()
    return json.loads(text)


def research(brand, post):
    """Google Search se trending angles/hashtags (optional; fail ho to khali)."""
    if os.getenv("USE_SEARCH", "1") != "1":
        return ""
    prompt = (
        f"Business: {brand.get('brand_name')} ({brand.get('industry')}).\n"
        f"Post topic: {post.get('Topic')}. Audience: {post.get('Audience') or brand.get('audience_default')}.\n"
        "Search the web. Give me: (1) 8 currently popular Instagram/Facebook hashtags for this niche "
        "(mix broad, mid, niche), (2) 6 keywords people search for around this topic, "
        "(3) one trending angle or hook idea. Keep it short, plain text."
    )
    try:
        r = client().models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        return r.text or ""
    except Exception as e:
        print("Research skip:", type(e).__name__, flush=True)
        return ""


def _brand_block(brand):
    return (
        f"Brand: {brand.get('brand_name')}\nAbout: {brand.get('about')}\n"
        f"Industry: {brand.get('industry')}\nTone: {brand.get('tone')}\n"
        f"Language: {brand.get('language')}\nDefault CTA: {brand.get('cta')}\n"
        f"Contact: {brand.get('contact')}\n"
        f"Never talk about: {brand.get('forbidden_topics')}"
    )


def clean_tags(tags, limit=15):
    out, seen = [], set()
    for t in tags:
        t = "#" + re.sub(r"[^\w]", "", str(t).lstrip("#"), flags=re.UNICODE)
        if len(t) > 1 and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:limit]


def build_post(brand, post, research_text, n_slides=1):
    system = (
        "You are a senior social media strategist and copywriter. "
        "Write posts that earn real engagement honestly. No false claims, no fake urgency, "
        "no promises you can't verify. Reply with JSON only.\n\n" + _brand_block(brand)
    )
    slides_spec = ""
    if n_slides > 1:
        slides_spec = (f"\n- slides: list of EXACTLY {n_slides} objects {{\"title\": max 8 words, \"body\": max 22 words}}. "
                       "Slide 1 = scroll-stopping hook (cover), middle slides = one clear idea each, last = call to action. "
                       "The caption must invite people to swipe.")
    prompt = f"""Create today's post.
Topic: {post.get('Topic')}
Audience: {post.get('Audience') or brand.get('audience_default')}
Image idea: {post.get('ImageIdea')}
Headline given by client (use exactly if not empty): {post.get('Headline')}
Subtext given by client (use exactly if not empty): {post.get('Subtext')}

Research notes (may be empty):
{research_text}

Return JSON with keys:
- headline: max 8 words, punchy, for the image (if the client's art-direction names a big word, use that)
- subtext: max 14 words, for the image
- caption: strong first-line hook, short paragraphs, 1-2 emojis max, ends with the CTA. 60-130 words. Written in: {brand.get('language')}
- hashtags: list of 12-15 hashtags (5 niche, 5 mid-size, 3 broad), relevant to audience
- keywords: list of 5 keywords naturally woven into the caption
- image_prompt: English, one sentence, describes a clean photographic/illustration background WITHOUT any text or logos{slides_spec}
"""
    d = ask_json(prompt, system)
    d["hashtags"] = clean_tags(d.get("hashtags", []))
    if n_slides > 1:
        sl = [x for x in d.get("slides", []) if isinstance(x, dict) and x.get("title")]
        d["slides"] = sl[:n_slides] if len(sl) >= 2 else None
    return d


def safety_check(brand, headline, caption):
    prompt = f"""You are a strict brand-safety reviewer for {brand.get('brand_name')}.
Never-talk-about list: {brand.get('forbidden_topics')}
Check this post for: hate/abuse, adult content, misleading or unverifiable claims, medical/financial guarantees,
religion/politics, anything off-brand or embarrassing.
Headline: {headline}
Caption: {caption}
Reply JSON: {{"safe": true/false, "reason": "short reason"}}"""
    return ask_json(prompt, temperature=0.1)


def triage(brand, faq, kind, text, author):
    system = (
        "You manage the inbox of a business on Instagram/Facebook. Reply JSON only.\n\n"
        + _brand_block(brand)
        + "\n\nFAQ (the ONLY source for facts like prices, timings, policies):\n" + faq
    )
    prompt = f"""Incoming {kind} from "{author}":
\"\"\"{text}\"\"\"

Rules:
- category: one of question, praise, complaint, spam, sensitive, other
- needs_human = true for complaints, refunds, legal, anger, health/safety, payment disputes, or any question the FAQ cannot answer.
- spam/abuse/trolling: category spam, reply empty.
- Otherwise write a warm, short reply (comments: 1-2 lines, DMs: up to 4 lines) in the SAME language/script as the sender.
- Never invent prices, dates, discounts or promises. If unsure, say the team will follow up and share contact: {brand.get('contact')}.
JSON: {{"category": "...", "needs_human": true/false, "reply": "..."}}"""
    return ask_json(prompt, system, temperature=0.4)
