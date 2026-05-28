"""
Keystone — Policy Logic Diagnostic Tool
FastAPI backend: Gemini AI proxy
"""

import os
import json
import re
from dataclasses import dataclass
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
import google.generativeai as genai

# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Keystone AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── Gemini Setup ───────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# ── Request Models ─────────────────────────────────────────────────────────────
@dataclass
class SuggestComponentsRequest:
    initiative_description: str
    mandate: str = "Service Delivery"


@dataclass
class AuditNarrativeRequest:
    project_name: str
    department: str
    mandate: str
    health_score: int
    audit_findings: list  # list of {errorType, riskLevel, message, componentDescription}
    components: list      # list of {type, description, targetBenchmark, verificationSource}


@dataclass
class VerificationSuggestionsRequest:
    component_description: str
    component_type: str   # "Output" or "Outcome"
    mandate: str
    project_name: str


@dataclass
class ImproveDescriptionRequest:
    description: str
    component_type: str   # "Input" | "Activity" | "Output" | "Outcome"
    mandate: str


@dataclass
class NaturalLanguageProjectRequest:
    user_input: str


# ── Helper: safe JSON parse from Gemini response ───────────────────────────────
def extract_json(text: str):
    """Strip markdown code fences and parse JSON from Gemini response."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ── Endpoint 1: AI Component Suggester ────────────────────────────────────────
@app.post("/api/ai/suggest-components")
async def suggest_components(req: SuggestComponentsRequest):
    """
    Given a plain-text description of a policy initiative, generate a full
    set of Inputs, Activities, Outputs, and Outcomes.
    """
    prompt = f"""You are an expert Canadian government policy analyst specialising in logic models and programme theory.

A policy analyst has described their initiative as follows:
"{req.initiative_description}"

Mandate classification: {req.mandate}

Generate a realistic, professional logic model for this initiative. Return ONLY a valid JSON object with this exact structure — no markdown, no explanation:

{{
  "inputs": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}
  ],
  "activities": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}
  ],
  "outputs": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}
  ],
  "outcomes": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}
  ]
}}

Rules:
- Generate 2–3 items per category
- Descriptions must be specific, professional, and evaluable
- Target benchmarks must be measurable (quantities, dates, percentages)
- Verification sources must name real mechanisms (e.g., Treasury Board submission, FNHA quarterly report, BC Gazette, community survey instrument)
- For DRIPA Alignment or Self-Government Transition mandates, reference Indigenous governance bodies, OCAP principles, and Nation-specific data stewardship where appropriate
- Use formal Canadian government policy language
- Return ONLY the JSON object, nothing else"""

    try:
        response = model.generate_content(prompt)
        data = extract_json(response.text)
        return {"success": True, "data": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 2: AI Audit Narrative ────────────────────────────────────────────
@app.post("/api/ai/audit-narrative")
async def audit_narrative(req: AuditNarrativeRequest):
    """
    After the rule-based audit runs, generate a plain-English diagnostic
    narrative suitable for a Deputy Minister or senior decision-maker.
    """
    findings_text = "\n".join([
        f"- [{f['riskLevel']} / {f['errorType']}] {f['message']} (Component: {f.get('componentDescription', 'N/A')})"
        for f in req.audit_findings
    ]) if req.audit_findings else "No risk flags detected."

    components_text = "\n".join([
        f"- [{c['type']}] {c['description']}"
        for c in req.components
    ])

    prompt = f"""You are a senior policy evaluation advisor writing for a Deputy Minister audience.

Project: {req.project_name}
Department: {req.department}
Mandate: {req.mandate}
Health Score: {req.health_score}/100

Logic Model Components:
{components_text}

Audit Findings:
{findings_text}

Write a 2–3 paragraph plain-English diagnostic narrative that:
1. Opens with a one-sentence overall assessment of the logic model's structural integrity
2. Explains what the specific risk flags mean in the context of THIS project (not generic definitions)
3. Closes with a concrete, prioritised recommendation for the analyst's next action

Tone: professional, direct, non-jargon where possible. Write as if briefing a senior official who has 90 seconds to read this.
Do NOT use bullet points. Write in flowing paragraphs only.
Do NOT repeat the flag names verbatim — translate them into plain language.
Return ONLY the narrative text, no headings, no markdown."""

    try:
        response = model.generate_content(prompt)
        return {"success": True, "narrative": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 3: Smart Verification Source Suggestions ─────────────────────────
@app.post("/api/ai/verification-suggestions")
async def verification_suggestions(req: VerificationSuggestionsRequest):
    """
    When a Blind Spot is flagged, suggest 3 specific verification sources
    appropriate to the component type and mandate.
    """
    prompt = f"""You are a Canadian government policy evaluation specialist.

A policy framework component has been flagged because it has no verification source defined.

Project: {req.project_name}
Mandate: {req.mandate}
Component type: {req.component_type}
Component description: "{req.component_description}"

Suggest exactly 3 specific, realistic data collection mechanisms or verification sources for this component.

Return ONLY a valid JSON array with this structure — no markdown, no explanation:
[
  {{"source": "...", "rationale": "..."}},
  {{"source": "...", "rationale": "..."}},
  {{"source": "...", "rationale": "..."}}
]

Rules:
- Each source must be a named, real mechanism (e.g., "BC Gazette publication", "FNHA quarterly reporting dashboard", "Treasury Board Submission #XXXX", "Nation-controlled data stewardship committee confirmation")
- For DRIPA Alignment or Self-Government Transition mandates, at least one suggestion must reference a Nation-controlled or OCAP-compliant data source
- The rationale must be one sentence explaining why this source is appropriate for this specific component
- Return ONLY the JSON array, nothing else"""

    try:
        response = model.generate_content(prompt)
        data = extract_json(response.text)
        return {"success": True, "suggestions": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 4: Component Description Improver ────────────────────────────────
@app.post("/api/ai/improve-description")
async def improve_description(req: ImproveDescriptionRequest):
    """
    Rewrite a vague component description into precise, evaluable policy language.
    """
    prompt = f"""You are a Canadian government policy writing specialist with expertise in logic models and programme evaluation.

A policy analyst has written this {req.component_type} description for a {req.mandate} initiative:
"{req.description}"

Rewrite it to meet professional policy evaluation standards:
- Make it specific and evaluable (a reviewer should be able to confirm whether it was achieved)
- Use active voice and precise language
- For {req.component_type} components specifically: {"include the resource type, quantity, and timeframe" if req.component_type == "Input" else "describe the concrete action, who performs it, and the expected scale" if req.component_type == "Activity" else "name the specific deliverable, its form, and who receives it" if req.component_type == "Output" else "describe the systemic change, who benefits, and the scope of impact"}
- Keep it to 1–2 sentences maximum
- Maintain the original intent — do not change what the component is about

Return ONLY the improved description text, no explanation, no quotes, no markdown."""

    try:
        response = model.generate_content(prompt)
        return {"success": True, "improved": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 5: Natural Language Project Creation ─────────────────────────────
@app.post("/api/ai/create-project")
async def create_project(req: NaturalLanguageProjectRequest):
    """
    Parse a plain-text description of a policy initiative and extract
    structured project fields.
    """
    prompt = f"""You are a Canadian government policy analyst assistant.

A user has described their policy initiative in plain language:
"{req.user_input}"

Extract the following project fields from this description. If a field cannot be confidently inferred, generate a reasonable professional default.

Return ONLY a valid JSON object with this exact structure — no markdown, no explanation:
{{
  "name": "...",
  "department": "...",
  "description": "...",
  "mandate": "..."
}}

Rules:
- "name": A formal, title-case project name (e.g., "Wet'suwet'en Nation Child Welfare Jurisdiction Agreement")
- "department": The most likely BC or federal government department responsible (e.g., "BC Ministry of Children and Family Development", "BC Ministry of Indigenous Relations and Reconciliation")
- "description": 1–2 sentences describing the initiative in formal policy language
- "mandate": MUST be exactly one of: "DRIPA Alignment", "Self-Government Transition", "Service Delivery", "Economic Development"
  - Use "DRIPA Alignment" if the initiative involves joint decision-making, Section 7 agreements, or UNDRIP implementation
  - Use "Self-Government Transition" if it involves transferring jurisdiction, governance authority, or self-determination
  - Use "Service Delivery" if it involves program delivery, health, education, or social services
  - Use "Economic Development" if it involves economic opportunities, land use revenue, or business development
- Return ONLY the JSON object, nothing else"""

    try:
        response = model.generate_content(prompt)
        data = extract_json(response.text)
        # Validate mandate value
        valid_mandates = ["DRIPA Alignment", "Self-Government Transition", "Service Delivery", "Economic Development"]
        if data.get("mandate") not in valid_mandates:
            data["mandate"] = "DRIPA Alignment"
        return {"success": True, "project": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "model": "gemini-1.5-flash"}


# ── Serve Static Frontend ──────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")
