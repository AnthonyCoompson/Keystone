"""
Keystone — AI Processor
© 2026 Anthony Coompson. All rights reserved.

Handles all Gemini API communication for the Keystone backend.
Imported by main.py — never called directly.

Uses the official google-genai SDK (v2+) which routes through the
stable v1 API endpoint. The older google-generativeai SDK (0.8.x)
was locked to v1beta where current model names are not available.
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
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
_client = None
_MODEL  = "gemini-2.5-flash"

# Keystone deals heavily in government/policy/Indigenous-rights subject matter.
# Gemini's default safety thresholds (especially CIVIC_INTEGRITY and
# HARASSMENT) can mis-flag entirely legitimate policy text — e.g. discussion
# of jurisdiction, land claims, or treaty rights — and cut a response short
# with finish_reason=SAFETY. Relax these to BLOCK_ONLY_HIGH so policy content
# isn't blocked, while still blocking genuinely high-severity content.
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

_CONFIG = types.GenerateContentConfig(
    temperature=0.4,
    max_output_tokens=8192,
    safety_settings=_SAFETY_SETTINGS,
)

def _init():
    global _client
    if not _GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. All AI endpoints will return 503.")
        return
    try:
        _client = genai.Client(api_key=_GEMINI_API_KEY)
        logger.info(f"✓ Gemini client initialised (model: {_MODEL}).")
    except Exception as exc:
        logger.error(f"Gemini init failed: {exc}")

_init()


# ── Public helpers ─────────────────────────────────────────────────────────────

def is_ready() -> bool:
    """Return True if the Gemini client is initialised and ready."""
    return _client is not None


def require_client():
    """Return the client or raise a 503 with a clear message."""
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
    """
    Log finish_reason / safety_ratings for a response so that early or
    blocked generations (SAFETY, RECITATION, MAX_TOKENS, PROHIBITED_CONTENT,
    etc.) are visible in the Render logs instead of surfacing only as a
    generic 'invalid JSON' error.
    """
    try:
        candidates = response.candidates or []
        for c in candidates:
            reason = getattr(c, "finish_reason", None)
            if reason is not None and str(reason) != "FinishReason.STOP":
                logger.warning(
                    f"[{context}] Gemini finish_reason={reason} "
                    f"(token_count={getattr(c, 'token_count', '?')}). "
                    f"safety_ratings={getattr(c, 'safety_ratings', None)}"
                )
        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None:
            block_reason = getattr(feedback, "block_reason", None)
            if block_reason:
                logger.warning(f"[{context}] prompt_feedback.block_reason={block_reason}")
    except Exception as diag_exc:
        logger.debug(f"[{context}] Could not read response diagnostics: {diag_exc}")


# Gemini occasionally returns 503 UNAVAILABLE ("model is currently
# experiencing high demand") or other 5xx errors during traffic spikes.
# These are transient and typically clear within a few seconds, so retry
# with exponential backoff before giving up.
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2  # seconds


def _call_with_retry(fn, context: str):
    """Call fn() with retries on transient Gemini ServerError (5xx)."""
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except errors.ServerError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"[{context}] Gemini server error (attempt {attempt + 1}/{_MAX_RETRIES}): "
                    f"{exc}. Retrying in {delay}s…"
                )
                time.sleep(delay)
            else:
                logger.error(f"[{context}] Gemini server error after {_MAX_RETRIES} attempts: {exc}")
    raise last_exc


def generate_text(prompt: str) -> str:
    """Send a plain-text prompt to Gemini and return the raw response string."""
    client = require_client()
    try:
        response = _call_with_retry(
            lambda: client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=_CONFIG,
            ),
            "generate_text",
        )
        _log_response_diagnostics(response, "generate_text")
        text = response.text
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text
    except HTTPException:
        raise
    except errors.ServerError as exc:
        logger.error(f"Gemini generate_text failed after retries: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Gemini's servers are currently overloaded (high demand). Please try again in a moment.",
        )
    except Exception as exc:
        logger.error(f"Gemini generate_text failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Gemini error: {str(exc)}")


def generate_with_file(prompt: str, mime_type: str, base64_data: str) -> str:
    """
    Send a prompt alongside an inline file (e.g. a PDF) to Gemini.
    Used by the Document Analysis endpoint.
    """
    client = require_client()
    try:
        raw_bytes = base64.b64decode(base64_data)
        file_part = types.Part.from_bytes(data=raw_bytes, mime_type=mime_type)
        response = _call_with_retry(
            lambda: client.models.generate_content(
                model=_MODEL,
                contents=[file_part, prompt],
                config=_CONFIG,
            ),
            "generate_with_file",
        )
        _log_response_diagnostics(response, "generate_with_file")
        text = response.text
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text
    except HTTPException:
        raise
    except errors.ServerError as exc:
        logger.error(f"Gemini generate_with_file failed after retries: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Gemini's servers are currently overloaded (high demand). Please try again in a moment.",
        )
    except Exception as exc:
        logger.error(f"Gemini generate_with_file failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Gemini error: {str(exc)}")


def parse_json(text: str) -> dict | list:
    """
    Strip markdown code fences from a Gemini response and parse JSON.
    Raises HTTPException 502 if the text is not valid JSON after stripping.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?[ \t]*\n?", "", cleaned)
    cleaned = re.sub(r"\n?[ \t]*```\s*$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(f"JSON parse failed. Raw Gemini output:\n{text[:500]}")
        raise HTTPException(
            status_code=502,
            detail=f"Gemini returned text that is not valid JSON: {str(exc)}",
        )


def generate_json(prompt: str) -> dict | list:
    """Convenience: generate text from a prompt and parse the result as JSON."""
    text = generate_text(prompt)
    return parse_json(text)


def generate_json_with_file(prompt: str, mime_type: str, base64_data: str) -> dict | list:
    """Convenience: generate text with an inline file and parse the result as JSON."""
    text = generate_with_file(prompt, mime_type, base64_data)
    return parse_json(text)
