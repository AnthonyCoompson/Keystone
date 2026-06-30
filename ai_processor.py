"""
Keystone — AI Processor
© 2026 Anthony Coompson. All rights reserved.

Handles all Gemini API communication for the Keystone backend.
Imported by main.py — never called directly.
"""

import os
import json
import re
import time
import base64
import logging
from fastapi import HTTPException
from google import genai
from google.genai import types, errors

logger = logging.getLogger("keystone.ai")

# ── Initialise Gemini ──────────────────────────────────────────────────────────
_GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "").strip()
_client          = None
_MODEL           = "gemini-2.5-flash"   # primary
_MODEL_FALLBACK  = "gemini-1.5-flash"   # used on final retry attempts when primary is overloaded

# Keystone deals in government/policy/Indigenous-rights subject matter.
# Gemini's default safety thresholds can mis-flag legitimate policy text —
# e.g. jurisdiction, land claims, treaty rights — so relax to BLOCK_ONLY_HIGH.
_SAFETY_SETTINGS = [
    types.SafetySetting(category=cat, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH)
    for cat in (
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
    )
]

# Standard config — text narrative, descriptions, short JSON responses.
_CONFIG = types.GenerateContentConfig(
    temperature=0.4,
    max_output_tokens=8192,
    safety_settings=_SAFETY_SETTINGS,
)

# Large-JSON config — timeline, TB submission, component suggestion, document
# extraction. Two key differences from _CONFIG:
#   1. response_mime_type="application/json": Gemini uses a different (more
#      efficient) token budget for structured output and does NOT truncate
#      mid-object the way free-text JSON generation can.
#   2. max_output_tokens=16384: accommodates large logic models (40+ components
#      each with multiple fields).
_CONFIG_JSON = types.GenerateContentConfig(
    temperature=0.3,
    max_output_tokens=16384,
    response_mime_type="application/json",
    safety_settings=_SAFETY_SETTINGS,
)


def _init():
    global _client
    if not _GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. All AI endpoints will return 503.")
        return
    try:
        _client = genai.Client(api_key=_GEMINI_API_KEY)
        logger.info(f"✓ Gemini client initialised (primary: {_MODEL}, fallback: {_MODEL_FALLBACK}).")
    except Exception as exc:
        logger.error(f"Gemini init failed: {exc}")

_init()


# ── Public helpers ─────────────────────────────────────────────────────────────

def is_ready() -> bool:
    return _client is not None


def require_client():
    if _client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API key is not configured on the server. "
                "Add GEMINI_API_KEY to your Render environment variables and redeploy."
            ),
        )
    return _client


def _log_response_diagnostics(response, context: str):
    try:
        for c in (response.candidates or []):
            reason = getattr(c, "finish_reason", None)
            if reason is not None and str(reason) != "FinishReason.STOP":
                logger.warning(
                    f"[{context}] finish_reason={reason} "
                    f"token_count={getattr(c, 'token_count', '?')} "
                    f"safety={getattr(c, 'safety_ratings', None)}"
                )
        feedback = getattr(response, "prompt_feedback", None)
        if feedback:
            block = getattr(feedback, "block_reason", None)
            if block:
                logger.warning(f"[{context}] prompt_feedback.block_reason={block}")
    except Exception as e:
        logger.debug(f"[{context}] diagnostics read failed: {e}")


# Retry strategy:
#   Attempts 1–3  → primary model  (gemini-2.5-flash), backoff 2s/4s/8s
#   Attempts 4–5  → fallback model (gemini-1.5-flash), less congested
_MAX_RETRIES     = 5
_RETRY_BASE_DELAY = 2  # seconds


def _call_with_retry(fn, context: str, fn_fallback=None):
    """
    Call fn() with up to _MAX_RETRIES attempts on transient ServerError (5xx).
    On attempts 4+ switches to fn_fallback (if provided) — typically the same
    call but targeting _MODEL_FALLBACK.
    """
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        use_fallback = fn_fallback and attempt >= 3
        if use_fallback:
            logger.info(f"[{context}] attempt {attempt+1}: switching to fallback model ({_MODEL_FALLBACK})")
        try:
            return (fn_fallback if use_fallback else fn)()
        except errors.ServerError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (2 ** min(attempt, 3))  # cap at 16s
                logger.warning(
                    f"[{context}] ServerError attempt {attempt+1}/{_MAX_RETRIES}: {exc}. "
                    f"Retrying in {delay}s…"
                )
                time.sleep(delay)
            else:
                logger.error(f"[{context}] failed after {_MAX_RETRIES} attempts: {exc}")
    raise last_exc


# ── Text generation ────────────────────────────────────────────────────────────

def generate_text(prompt: str) -> str:
    """Plain-text prompt → raw response string. Uses standard config."""
    client = require_client()
    try:
        response = _call_with_retry(
            lambda: client.models.generate_content(model=_MODEL,         contents=prompt, config=_CONFIG),
            "generate_text",
            lambda: client.models.generate_content(model=_MODEL_FALLBACK, contents=prompt, config=_CONFIG),
        )
        _log_response_diagnostics(response, "generate_text")
        text = response.text
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text
    except HTTPException:
        raise
    except errors.ServerError as exc:
        logger.error(f"generate_text failed after retries: {exc}")
        raise HTTPException(status_code=503, detail="Gemini is currently overloaded. Please try again in a moment.")
    except Exception as exc:
        logger.error(f"generate_text failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}")


def generate_text_large(prompt: str) -> str:
    """
    Like generate_text but uses _CONFIG_JSON (application/json + 16384 tokens).
    Use for endpoints that return large JSON objects: timeline, TB submission,
    component suggestion, document extraction.
    """
    client = require_client()
    try:
        response = _call_with_retry(
            lambda: client.models.generate_content(model=_MODEL,         contents=prompt, config=_CONFIG_JSON),
            "generate_text_large",
            lambda: client.models.generate_content(model=_MODEL_FALLBACK, contents=prompt, config=_CONFIG_JSON),
        )
        _log_response_diagnostics(response, "generate_text_large")
        text = response.text
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text
    except HTTPException:
        raise
    except errors.ServerError as exc:
        logger.error(f"generate_text_large failed after retries: {exc}")
        raise HTTPException(status_code=503, detail="Gemini is currently overloaded. Please try again in a moment.")
    except Exception as exc:
        logger.error(f"generate_text_large failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}")


def generate_with_file(prompt: str, mime_type: str, base64_data: str) -> str:
    """Send prompt + inline file (PDF/DOCX bytes) to Gemini. Used by Document Analysis."""
    client = require_client()
    try:
        raw_bytes = base64.b64decode(base64_data)
        file_part = types.Part.from_bytes(data=raw_bytes, mime_type=mime_type)
        response = _call_with_retry(
            lambda: client.models.generate_content(model=_MODEL,         contents=[file_part, prompt], config=_CONFIG),
            "generate_with_file",
            lambda: client.models.generate_content(model=_MODEL_FALLBACK, contents=[file_part, prompt], config=_CONFIG),
        )
        _log_response_diagnostics(response, "generate_with_file")
        text = response.text
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text
    except HTTPException:
        raise
    except errors.ServerError as exc:
        logger.error(f"generate_with_file failed after retries: {exc}")
        raise HTTPException(status_code=503, detail="Gemini is currently overloaded. Please try again in a moment.")
    except Exception as exc:
        logger.error(f"generate_with_file failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Gemini error: {exc}")


# ── JSON helpers ───────────────────────────────────────────────────────────────

def parse_json(text: str) -> dict | list:
    """Strip markdown fences and parse JSON. Raises 502 on parse failure."""
    cleaned = re.sub(r"^```(?:json)?[ \t]*\n?", "", text.strip())
    cleaned = re.sub(r"\n?[ \t]*```\s*$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(f"JSON parse failed. Raw output:\n{text[:500]}")
        raise HTTPException(status_code=502, detail=f"Gemini returned invalid JSON: {exc}")


def generate_json(prompt: str) -> dict | list:
    """Standard text → JSON. For short/medium JSON responses."""
    return parse_json(generate_text(prompt))


def generate_json_large(prompt: str) -> dict | list:
    """Large-config text → JSON. For timeline, TB submission, extraction, suggestion."""
    return parse_json(generate_text_large(prompt))


def generate_json_with_file(prompt: str, mime_type: str, base64_data: str) -> dict | list:
    """File + prompt → JSON. For document extraction with raw PDF bytes."""
    return parse_json(generate_with_file(prompt, mime_type, base64_data))
