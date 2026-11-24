import json
import os
import re
import time
import requests

from google import genai
from google.genai import types

from .config import GEMINI_MODEL

_client = None

PREFERRED_GEMINI_MODELS = [
    GEMINI_MODEL,
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

GROQ_FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]


def _candidate_models():
    out, seen = [], set()
    for m in PREFERRED_GEMINI_MODELS:
        name = (m or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def client():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"].strip(),
            http_options=types.HttpOptions(timeout=12000),
        )
    return _client


def _groq_fallback(prompt, system=None, temperature=0.7, json_mode=False):
    groq_key = re.sub(r"\s+", "", os.getenv("GROQ_API_KEY", ""))
    if not groq_key:
        raise RuntimeError("Gemini failed/quota exhausted and GROQ_API_KEY is not set.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_err = None
    for model_name in GROQ_FALLBACK_MODELS:
        try:
            print(f"Switching to Groq fallback ({model_name})...", flush=True)
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=25,
            )
            if resp.status_code >= 400:
                print(f"Groq {model_name} HTTP {resp.status_code}: {resp.text[:250]}", flush=True)
                resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            continue

    raise last_err


def _extract_json(raw_text):
    text = (raw_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _generate_with_fallback(prompt, config, system=None, temperature=0.7, json_mode=False):
    last_err = None
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY", "").strip())

    if has_gemini_key:
        for model_name in _candidate_models():
            try:
                print(f"Trying Gemini model: {model_name}", flush=True)
                r = client().models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                if r.text:
                    return r.text
            except Exception as e:
                last_err = e
                print(f"Model {model_name} failed: {type(e).__name__}", flush=True)
                continue

    if os.getenv("GROQ_API_KEY", "").strip():
        return _groq_fallback(prompt, system=system, temperature=temperature, json_mode=json_mode)

    if last_err:
        raise last_err
    raise RuntimeError("No AI provider succeeded.")


def ask_json(prompt, system=None, temperature=0.8):
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
    )
    raw = _generate_with_fallback(
        prompt, cfg, system=system, temperature=temperature, json_mode=True
    )
    return _extract_json(raw)


def research(brand, post):
    """Google Search se trending angles/hashtags (optional; fail ho to khali)."""
    if os.getenv("USE_SEARCH", "1") != "1":
        return ""
    if not os.getenv("GEMINI_API_KEY", "").strip():
        return ""
    prompt = (
        f"Business:
