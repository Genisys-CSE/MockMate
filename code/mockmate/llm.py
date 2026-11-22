"""Thin wrapper around the Gemini API (google-genai SDK).

The API key is read from (in order): Streamlit secrets, the GEMINI_API_KEY
environment variable, or a local .env file. It is never written to the repo.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass

from google import genai
from google.genai import types

from .prompts import ROOT

# Free tier (Nov 2026): 3.5 Flash-Lite = 500 requests/day, 15/min. The bigger
# "Flash" models allow only 20 requests/day, too few for a public demo.
MODEL = os.environ.get("MOCKMATE_MODEL", "gemini-3.5-flash-lite")
# used only if the main model's daily quota is used up
FALLBACK_MODELS = ["gemini-3.1-flash-lite"]
OPEN_MODEL = "gemma-4-31b-it"  # open-weights model used for the cross-model check

_client = None


def _load_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
    try:  # Streamlit Cloud secrets
        import streamlit as st

        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def set_key(key: str) -> None:
    global _client
    os.environ["GEMINI_API_KEY"] = key.strip()
    _client = None


def has_key() -> bool:
    return bool(_load_key())


_lock = threading.Lock()


def client() -> genai.Client:
    """One shared client, created once under a lock (threads in the test
    scripts must not replace it while another thread is using it)."""
    global _client
    with _lock:
        if _client is None:
            key = _load_key()
            if not key:
                raise RuntimeError("No GEMINI_API_KEY found (Streamlit secrets, env var or .env).")
            _client = genai.Client(api_key=key)
        return _client


@dataclass
class LLMResult:
    text: str
    parsed: object | None
    model: str
    latency_s: float
    error: str | None = None


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        return m.group(1).strip()
    # fall back to the first {...} block
    a, b = text.find("{"), text.rfind("}")
    return text[a : b + 1] if a != -1 and b > a else text


def try_json(text: str):
    try:
        return json.loads(_strip_fences(text))
    except Exception:
        return None


def generate(
    system: str,
    user: str,
    temperature: float | None = None,
    schema=None,
    json_mode: bool = False,
    model: str | None = None,
    retries: int = 5,
) -> LLMResult:
    """One LLM call with retry on rate limits / server errors."""
    allow_fallback = model is None
    model = model or MODEL
    is_gemma = model.startswith("gemma")
    cfg = {}
    if temperature is not None:
        cfg["temperature"] = temperature
    if is_gemma:
        # Gemma via the API: no system instruction / schema support, so the
        # system text is sent at the top of the user turn.
        contents = (system + "\n\n" + user) if system else user
    else:
        contents = user
        if system:
            cfg["system_instruction"] = system
        if schema is not None:
            cfg["response_mime_type"] = "application/json"
            cfg["response_schema"] = schema
        elif json_mode:
            cfg["response_mime_type"] = "application/json"
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level="low")

    last_err = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            resp = client().models.generate_content(
                model=model, contents=contents, config=types.GenerateContentConfig(**cfg)
            )
            text = resp.text or ""
            parsed = None
            if schema is not None and getattr(resp, "parsed", None) is not None:
                p = resp.parsed
                parsed = p.model_dump() if hasattr(p, "model_dump") else p
            elif schema is not None or json_mode:
                parsed = try_json(text)
            return LLMResult(text=text, parsed=parsed, model=model, latency_s=round(time.time() - t0, 2))
        except Exception as e:  # rate limit / overload -> back off and retry
            last_err = str(e)
            msg = last_err.lower()
            if "client has been closed" in msg:
                time.sleep(1)
                continue
            if "thinking" in msg and "thinking_config" in cfg:
                cfg.pop("thinking_config")  # model does not support thinking level
                continue
            if "per day" in msg or "perday" in msg:
                # daily quota gone: switch to the next model instead of waiting hours
                if allow_fallback and model in [MODEL] + FALLBACK_MODELS[:-1]:
                    chain_ = [MODEL] + FALLBACK_MODELS
                    model = chain_[chain_.index(model) + 1]
                    continue
                break
            if any(s in msg for s in ("429", "resource_exhausted", "503", "unavailable", "500", "deadline")):
                time.sleep(min(60, 8 * (attempt + 1)))
                continue
            break
    return LLMResult(text="", parsed=None, model=model, latency_s=0.0, error=last_err)
