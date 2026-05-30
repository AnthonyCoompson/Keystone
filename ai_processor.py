"""
Keystone — AI Processor
© 2026 Anthony Coompson. All rights reserved.

Handles all Gemini API communication for the Keystone backend.
Imported by main.py — never called directly.

Responsibilities:
  - Hold the configured Gemini model instance
  - Provide one generate() function that every endpoint calls
  - Parse Gemini responses (strip fences, validate JSON)
  - Raise clean HTTPExceptions that the frontend can display
"""

import os
import json
import re
import logging
from fastapi import HTTPException
import google.generativeai as genai

logger = logging.getLogger("keystone.ai")

# ── Initialise Gemini ──────────────────────────────────────────────────────────
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
_model = None

def _init():
    global _model
    if not _GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. All AI endpoints will return 503.")
        return
    try:
        genai.configure(api_key=_GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )
        logger.info("✓ Gemini model initialised (gemini-1.5-flash).")
    except Exception as exc:
        logger.error(f"Gemini init failed: {exc}")

_init()


# ── Public helpers ─────────────────────────────────────────────────────────────

def is_ready() -> bool:
    """Return True if the Gemini model is initialised and ready."""
    return _model is not None


def require_model():
    """
    Return the model or raise a 503 with a clear message.
    Call this at the top of every endpoint handler.
    """
    if _model is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API key is not configured on the server. "
                "Add GEMINI_API_KEY to your Render environment variables and redeploy."
            ),
        )
    return _model


def generate_text(prompt: str) -> str:
    """
    Send a plain-text prompt to Gemini and return the raw response string.
    Raises HTTPException on any Gemini-level error.
    """
    model = require_model()
    try:
        response = model.generate_content(prompt)
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
    model = require_model()
    try:
        response = model.generate_content([
            {"inline_data": {"mime_type": mime_type, "data": base64_data}},
            prompt,
        ])
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
    # Remove opening fence: ```json or ``` followed by optional whitespace/newline
    cleaned = re.sub(r"^```(?:json)?[ \t]*\n?", "", cleaned)
    # Remove closing fence: optional newline/whitespace then ```
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
