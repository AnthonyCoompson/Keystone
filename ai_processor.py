"""
Keystone — AI Processor
© 2026 Anthony Coompson. All rights reserved.

Handles all Gemini API communication for the Keystone backend.
Imported by main.py — never called directly.
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
        # gemini-1.5-flash-002 is the correct model name for google-generativeai==0.8.3
        _model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-002",
            generation_config=genai.GenerationConfig(
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )
        logger.info("✓ Gemini model initialised (gemini-1.5-flash-002).")
    except Exception as exc:
        logger.error(f"Gemini init failed: {exc}")

_init()


# ── Public helpers ─────────────────────────────────────────────────────────────

def is_ready() -> bool:
    return _model is not None


def require_model():
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
    text = generate_text(prompt)
    return parse_json(text)


def generate_json_with_file(prompt: str, mime_type: str, base64_data: str) -> dict | list:
    text = generate_with_file(prompt, mime_type, base64_data)
    return parse_json(text)
