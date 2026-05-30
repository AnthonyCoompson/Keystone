"""
Keystone — Policy Logic Diagnostic Tool
FastAPI backend: Gemini AI proxy
© 2026 Anthony Coompson. All rights reserved.
"""

import os
import json
import re
from typing import Optional, List, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import google.generativeai as genai

# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Keystone AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# ── Gemini Setup ───────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
gemini_model = None

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        print("✓ Gemini model initialised successfully.")
    except Exception as e:
        print(f"⚠ Gemini init failed: {e}")
else:
    print("⚠ GEMINI_API_KEY not set — AI endpoints will return 503.")


# ── Request Models (Pydantic — required for FastAPI body parsing) ──────────────
class ComponentItem(BaseModel):
    type: str = ""
    description: str = ""

class SuggestComponentsRequest(BaseModel):
    initiative_description: str
    mandate: str = "Service Delivery"
    existing_components: List[ComponentItem] = []

class AuditFinding(BaseModel):
    errorType: str = ""
    riskLevel: str = ""
    message: str = ""
    componentDescription: str = ""

class ComponentDetail(BaseModel):
    type: str = ""
    description: str = ""
    targetBenchmark: str = ""
    verificationSource: str = ""

class AuditNarrativeRequest(BaseModel):
    project_name: str
    department: str
    mandate: str
    health_score: int
    audit_findings: List[AuditFinding] = []
    components: List[ComponentDetail] = []

class VerificationSuggestionsRequest(BaseModel):
    component_description: str
    component_type: str
    mandate: str
    project_name: str

class ImproveDescriptionRequest(BaseModel):
    description: str
    component_type: str
    mandate: str

class NaturalLanguageProjectRequest(BaseModel):
    user_input: str

class ExtractComponentsRequest(BaseModel):
    document_text: str = ""
    document_base64: str = ""
    document_mime_type: str = "application/pdf"
    document_name: str = ""
    mandate: str = "Service Delivery"

class TimelineComponent(BaseModel):
    type: str = ""
    description: str = ""
    targetBenchmark: str = ""

class GenerateTimelineRequest(BaseModel):
    project_name: str
    mandate: str
    components: List[TimelineComponent] = []


# ── Helper: require Gemini model ───────────────────────────────────────────────
def require_gemini():
    if not gemini_model:
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured on server. Set the GEMINI_API_KEY environment variable in your Render dashboard."
        )
    return gemini_model


# ── Helper: safe JSON parse from Gemini response ───────────────────────────────
def extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ── Endpoint 1: AI Component Suggester ────────────────────────────────────────
@app.post("/api/ai/suggest-components")
async def suggest_components(req: SuggestComponentsRequest):
    model = require_gemini()

    existing_text = ""
    if req.existing_components:
        lines = [f"  - [{c.type}] {c.description}" for c in req.existing_components]
        existing_text = f"""
The analyst's logic model already contains the following components — do NOT duplicate or closely restate any of these:
{chr(10).join(lines)}

Generate only NEW components that complement and extend the existing model without overlap.
"""

    prompt = f"""You are an expert Canadian government policy analyst specialising in logic models and programme theory.

A policy analyst has described their initiative as follows:
"{req.initiative_description}"

Mandate classification: {req.mandate}
{existing_text}
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
- Generate 2-3 items per category
- Descriptions must be specific, professional, and evaluable
- Target benchmarks must be measurable (quantities, dates, percentages)
- Verification sources must name real mechanisms (e.g., Treasury Board submission, FNHA quarterly report, BC Gazette, community survey instrument)
- For DRIPA Alignment or Self-Government Transition mandates, reference Indigenous governance bodies, OCAP principles, and Nation-specific data stewardship
- Outcomes must describe systemic changes caused by the activities — not restate the activities themselves
- Return ONLY the JSON object, nothing else"""

    try:
        response = model.generate_content(prompt)
        data = extract_json(response.text)
        return {"success": True, "data": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 2: AI Audit Narrative ────────────────────────────────────────────
@app.post("/api/ai/audit-narrative")
async def audit_narrative(req: AuditNarrativeRequest):
    model = require_gemini()

    findings_text = "\n".join([
        f"- [{f.riskLevel} / {f.errorType}] {f.message} (Component: {f.componentDescription})"
        for f in req.audit_findings
    ]) if req.audit_findings else "No risk flags detected."

    components_text = "\n".join([f"- [{c.type}] {c.description}" for c in req.components])

    prompt = f"""You are a senior policy evaluation advisor writing for a Deputy Minister audience.

Project: {req.project_name}
Department: {req.department}
Mandate: {req.mandate}
Health Score: {req.health_score}/100

Logic Model Components:
{components_text}

Audit Findings:
{findings_text}

Error type reference (translate into plain language — never use technical names):
- Dead_End: activity with no deliverable or outcome — resources going nowhere
- Miracle_Leap: systemic outcome that activities are too weak to produce
- Blind_Spot: benchmark or outcome with no named tracking mechanism
- Circular_Logic: outcome essentially restates an activity
- Orphaned_Input: resource committed that no activity actually uses
- Scale_Mismatch: quantified outcome target with no activity-level benchmarks
- Duplicate_Component: two components of the same type that describe the same thing

Write a 2-3 paragraph plain-English diagnostic narrative that:
1. Opens with a one-sentence overall assessment of the logic model's structural integrity
2. Explains what the specific risk flags mean in the context of THIS project
3. Closes with a concrete, prioritised recommendation for the analyst's next action

Tone: professional, direct. No bullet points. No technical error type names verbatim. Return ONLY the narrative text."""

    try:
        response = model.generate_content(prompt)
        return {"success": True, "narrative": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 3: Smart Verification Source Suggestions ─────────────────────────
@app.post("/api/ai/verification-suggestions")
async def verification_suggestions(req: VerificationSuggestionsRequest):
    model = require_gemini()

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
- Each source must be a named, real mechanism
- For DRIPA Alignment or Self-Government Transition mandates, at least one suggestion must reference a Nation-controlled or OCAP-compliant data source
- The rationale must be one sentence explaining why this source is appropriate
- Return ONLY the JSON array, nothing else"""

    try:
        response = model.generate_content(prompt)
        data = extract_json(response.text)
        return {"success": True, "suggestions": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 4: Component Description Improver ────────────────────────────────
@app.post("/api/ai/improve-description")
async def improve_description(req: ImproveDescriptionRequest):
    model = require_gemini()

    type_guide = {
        "Input": "include the resource type, quantity, and timeframe",
        "Activity": "describe the concrete action, who performs it, and the expected scale",
        "Output": "name the specific deliverable, its form, and who receives it",
        "Outcome": "describe the systemic change, who benefits, and the scope of impact"
    }.get(req.component_type, "be specific and evaluable")

    prompt = f"""You are a Canadian government policy writing specialist with expertise in logic models.

A policy analyst has written this {req.component_type} description for a {req.mandate} initiative:
"{req.description}"

Rewrite it to meet professional policy evaluation standards:
- Make it specific and evaluable
- Use active voice and precise language
- For {req.component_type} components: {type_guide}
- Keep it to 1-2 sentences maximum
- Maintain the original intent

Return ONLY the improved description text, no explanation, no quotes, no markdown."""

    try:
        response = model.generate_content(prompt)
        return {"success": True, "improved": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 5: Natural Language Project Creation ─────────────────────────────
@app.post("/api/ai/create-project")
async def create_project(req: NaturalLanguageProjectRequest):
    model = require_gemini()

    prompt = f"""You are a Canadian government policy analyst assistant.

A user has described their policy initiative in plain language:
"{req.user_input}"

Extract the following project fields. If a field cannot be confidently inferred, generate a reasonable professional default.

Return ONLY a valid JSON object with this exact structure — no markdown, no explanation:
{{
  "name": "...",
  "department": "...",
  "description": "...",
  "mandate": "..."
}}

Rules:
- "name": A formal, title-case project name
- "department": The most likely BC or federal government department responsible
- "description": 1-2 sentences describing the initiative in formal policy language
- "mandate": MUST be exactly one of: "DRIPA Alignment", "Self-Government Transition", "Service Delivery", "Economic Development"
- Return ONLY the JSON object, nothing else"""

    try:
        response = model.generate_content(prompt)
        data = extract_json(response.text)
        valid_mandates = ["DRIPA Alignment", "Self-Government Transition", "Service Delivery", "Economic Development"]
        if data.get("mandate") not in valid_mandates:
            data["mandate"] = "DRIPA Alignment"
        return {"success": True, "project": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 6: Document Component Extraction ─────────────────────────────────
@app.post("/api/ai/extract-components")
async def extract_components(req: ExtractComponentsRequest):
    model = require_gemini()

    prompt_text = f"""You are an expert Canadian government policy analyst specialising in logic models.

A policy document has been provided. Extract all logic model components from it.

Document name: {req.document_name or "Untitled"}
Mandate classification: {req.mandate}

Return ONLY a valid JSON object with this exact structure — no markdown, no explanation:
{{
  "inputs": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "...", "sourceQuote": "..."}}
  ],
  "activities": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "...", "sourceQuote": "..."}}
  ],
  "outputs": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "...", "sourceQuote": "..."}}
  ],
  "outcomes": [
    {{"description": "...", "targetBenchmark": "...", "verificationSource": "...", "sourceQuote": "..."}}
  ]
}}

Rules:
- Extract only components explicitly stated or strongly implied
- sourceQuote: a short verbatim excerpt (max 80 chars) from the document
- If targetBenchmark or verificationSource are not in the document, leave them as empty strings
- Return ONLY the JSON object, nothing else"""

    try:
        if req.document_base64:
            response = model.generate_content([
                {"inline_data": {"mime_type": req.document_mime_type, "data": req.document_base64}},
                prompt_text
            ])
        else:
            full_prompt = prompt_text + f"\n\nDocument text:\n{req.document_text}"
            response = model.generate_content(full_prompt)
        data = extract_json(response.text)
        return {"success": True, "data": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint 7: Timeline Generation ───────────────────────────────────────────
@app.post("/api/ai/generate-timeline")
async def generate_timeline(req: GenerateTimelineRequest):
    model = require_gemini()

    components_text = "\n".join([
        f"- [{c.type}] {c.description}" + (f" (benchmark: {c.targetBenchmark})" if c.targetBenchmark else "")
        for c in req.components
    ])

    prompt = f"""You are a senior Canadian government programme manager creating a realistic project timeline.

Project: {req.project_name}
Mandate: {req.mandate}

Logic Model Components:
{components_text}

Create a realistic project timeline for these components. Weeks are relative to project start (Week 1 = project start).

Return ONLY a valid JSON object — no markdown, no explanation:
{{
  "total_weeks": 52,
  "phases": [
    {{"name": "Foundation", "start_week": 1, "end_week": 12, "color": "#1d4ed8"}},
    {{"name": "Implementation", "start_week": 13, "end_week": 40, "color": "#00c2ff"}},
    {{"name": "Evaluation", "start_week": 41, "end_week": 52, "color": "#10b981"}}
  ],
  "items": [
    {{
      "component_type": "Input",
      "description": "...",
      "start_week": 1,
      "end_week": 4,
      "phase": "Foundation",
      "is_milestone": false,
      "depends_on": null,
      "rationale": "one sentence explaining this timing"
    }}
  ],
  "critical_path_indices": [0, 2],
  "summary": "2-3 sentence plain-English explanation of the recommended timeline"
}}

Rules:
- Inputs always start at Week 1
- Activities follow Inputs; sequence them logically
- Outputs are milestones at the END of their producing Activities
- Outcomes sit in the final third of the timeline
- For DRIPA Alignment or Self-Government Transition, allow 12-24 months minimum for negotiation activities
- Return ONLY the JSON object"""

    try:
        response = model.generate_content(prompt)
        data = extract_json(response.text)
        return {"success": True, "timeline": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": "gemini-1.5-flash",
        "gemini_configured": bool(GEMINI_API_KEY)
    }


# ── Serve Static Frontend ──────────────────────────────────────────────────────
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/app.html")
async def serve_app():
    return FileResponse("app.html")

app.mount("/", StaticFiles(directory=".", html=True), name="static")
