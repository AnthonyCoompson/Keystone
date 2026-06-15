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
import base64
import logging
from fastapi import HTTPException
from google import genai
from google.genai import types

logger = logging.getLogger("keystone.ai")

# ── Initialise Gemini ──────────────────────────────────────────────────────────
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
_client = None
_MODEL  = "gemini-2.5-flash"
_CONFIG = types.GenerateContentConfig(
    temperature=0.4,
    max_output_tokens=2048,
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


def generate_text(prompt: str) -> str:
    """Send a plain-text prompt to Gemini and return the raw response string."""
    client = require_client()
    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=_CONFIG,
        )
        text = response.text
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text
    except HTTPException:
        raise
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
        response = client.models.generate_content(
            model=_MODEL,
            contents=[file_part, prompt],
            config=_CONFIG,
        )
        text = response.text
        if not text:
            raise ValueError("Gemini returned an empty response.")
        return text
    except HTTPException:
        raise
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
