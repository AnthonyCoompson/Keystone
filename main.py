"""
Keystone — Policy Logic Diagnostic Tool
FastAPI backend — routes all AI work through ai_processor.py
© 2026 Anthony Coompson. All rights reserved.
"""

import logging
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import ai_processor as ai

logging.basicConfig(level=logging.INFO)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Keystone AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request models (Pydantic — FastAPI requires these to parse JSON bodies) ────

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


# ── Endpoint 1: AI Component Suggester ────────────────────────────────────────
@app.post("/api/ai/suggest-components")
async def suggest_components(req: SuggestComponentsRequest):
    existing_text = ""
    if req.existing_components:
        lines = [f"  - [{c.type}] {c.description}" for c in req.existing_components]
        existing_text = (
            "\nThe analyst's logic model already contains these components — "
            "do NOT duplicate or closely restate any of them:\n"
            + "\n".join(lines)
            + "\nGenerate only NEW components that complement the existing model.\n"
        )

    prompt = f"""You are an expert Canadian government policy analyst specialising in logic models.

A policy analyst described their initiative:
"{req.initiative_description}"

Mandate classification: {req.mandate}
{existing_text}
Generate a realistic, professional logic model. Return ONLY a valid JSON object — no markdown, no explanation:

{{
  "inputs":    [{{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}],
  "activities":[{{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}],
  "outputs":   [{{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}],
  "outcomes":  [{{"description": "...", "targetBenchmark": "...", "verificationSource": "..."}}]
}}

Rules:
- 2-3 items per category
- Descriptions must be specific, professional, and evaluable
- Benchmarks must be measurable (quantities, dates, percentages)
- Verification sources must name real mechanisms (e.g. Treasury Board submission, FNHA quarterly report, BC Gazette)
- For DRIPA Alignment or Self-Government Transition mandates, reference Indigenous governance bodies and OCAP principles
- Outcomes must describe systemic changes — not restate the activities
- Return ONLY the JSON object"""

    data = ai.generate_json(prompt)
    return {"success": True, "data": data}


# ── Endpoint 2: AI Audit Narrative ────────────────────────────────────────────
@app.post("/api/ai/audit-narrative")
async def audit_narrative(req: AuditNarrativeRequest):
    findings_text = (
        "\n".join(
            f"- [{f.riskLevel} / {f.errorType}] {f.message} (Component: {f.componentDescription})"
            for f in req.audit_findings
        )
        if req.audit_findings
        else "No risk flags detected."
    )
    components_text = "\n".join(f"- [{c.type}] {c.description}" for c in req.components)

    prompt = f"""You are a senior policy evaluation advisor writing for a Deputy Minister audience.

Project: {req.project_name}
Department: {req.department}
Mandate: {req.mandate}
Health Score: {req.health_score}/100

Logic Model Components:
{components_text}

Audit Findings:
{findings_text}

Error type reference — translate into plain language, never use these technical names verbatim:
- Dead_End: activity with no deliverable or outcome attached
- Miracle_Leap: systemic outcome that the activities are too weak to produce
- Blind_Spot: benchmark or outcome with no named tracking mechanism
- Circular_Logic: outcome essentially restates an activity
- Orphaned_Input: resource committed that no activity actually uses
- Scale_Mismatch: quantified outcome target with no activity-level benchmarks
- Duplicate_Component: two components of the same type describing the same thing
- Timeframe_Mismatch: short-term outcome with high-leverage activities that need more than a year

Write a 2-3 paragraph plain-English diagnostic narrative:
1. One-sentence overall assessment of the logic model's structural integrity
2. What the specific risk flags mean in the context of THIS project (not generic definitions)
3. A concrete, prioritised recommendation for the analyst's next action

Tone: professional, direct. No bullet points. No technical error type names. Return ONLY the narrative text."""

    text = ai.generate_text(prompt)
    return {"success": True, "narrative": text.strip()}


# ── Endpoint 3: Smart Verification Source Suggestions ─────────────────────────
@app.post("/api/ai/verification-suggestions")
async def verification_suggestions(req: VerificationSuggestionsRequest):
    prompt = f"""You are a Canadian government policy evaluation specialist.

A framework component has been flagged because it has no verification source defined.

Project: {req.project_name}
Mandate: {req.mandate}
Component type: {req.component_type}
Component description: "{req.component_description}"

Suggest exactly 3 specific, realistic verification sources for this component.
Return ONLY a valid JSON array — no markdown, no explanation:
[
  {{"source": "...", "rationale": "..."}},
  {{"source": "...", "rationale": "..."}},
  {{"source": "...", "rationale": "..."}}
]

Rules:
- Each source must be a named, real mechanism (e.g. "BC Gazette publication", "FNHA quarterly reporting dashboard", "Treasury Board Submission")
- For DRIPA Alignment or Self-Government Transition mandates, at least one suggestion must reference a Nation-controlled or OCAP-compliant data source
- Rationale: one sentence explaining why this source fits this specific component
- Return ONLY the JSON array"""

    data = ai.generate_json(prompt)
    return {"success": True, "suggestions": data}


# ── Endpoint 4: Component Description Improver ────────────────────────────────
@app.post("/api/ai/improve-description")
async def improve_description(req: ImproveDescriptionRequest):
    type_guide = {
        "Input":    "include the resource type, quantity, and timeframe",
        "Activity": "describe the concrete action, who performs it, and the expected scale",
        "Output":   "name the specific deliverable, its form, and who receives it",
        "Outcome":  "describe the systemic change, who benefits, and the scope of impact",
    }.get(req.component_type, "be specific and evaluable")

    prompt = f"""You are a Canadian government policy writing specialist.

Rewrite this {req.component_type} description for a {req.mandate} initiative to be specific, evaluable, and professional.
For {req.component_type} components: {type_guide}.
Keep to 1-2 sentences. Maintain the original intent.

Original: "{req.description}"

Return ONLY the improved description — no quotes, no markdown, no explanation."""

    text = ai.generate_text(prompt)
    return {"success": True, "improved": text.strip()}


# ── Endpoint 5: Natural Language Project Creation ─────────────────────────────
@app.post("/api/ai/create-project")
async def create_project(req: NaturalLanguageProjectRequest):
    prompt = f"""You are a Canadian government policy analyst assistant.

Parse this plain-language description and extract structured project fields:
"{req.user_input}"

Return ONLY a valid JSON object — no markdown, no explanation:
{{
  "name":        "...",
  "department":  "...",
  "description": "...",
  "mandate":     "..."
}}

Rules:
- name: formal title-case project name
- department: the most likely BC or federal government department responsible
- description: 1-2 sentences in formal policy language
- mandate: MUST be exactly one of:
    "DRIPA Alignment" | "Self-Government Transition" | "Service Delivery" | "Economic Development"
  Use "DRIPA Alignment" for joint decision-making or UNDRIP implementation.
  Use "Self-Government Transition" for jurisdiction or governance transfer.
  Use "Service Delivery" for health, education, or social programmes.
  Use "Economic Development" for economic opportunities or land-use revenue.
- Return ONLY the JSON object"""

    data = ai.generate_json(prompt)
    valid_mandates = ["DRIPA Alignment", "Self-Government Transition", "Service Delivery", "Economic Development"]
    if data.get("mandate") not in valid_mandates:
        data["mandate"] = "DRIPA Alignment"
    return {"success": True, "project": data}


# ── Endpoint 6: Document Component Extraction ─────────────────────────────────
@app.post("/api/ai/extract-components")
async def extract_components(req: ExtractComponentsRequest):
    prompt = f"""You are an expert Canadian government policy analyst specialising in logic models.

A policy document has been provided. Extract all logic model components from it.

Document name: {req.document_name or "Untitled"}
Mandate classification: {req.mandate}

Return ONLY a valid JSON object — no markdown, no explanation:
{{
  "inputs":    [{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}],
  "activities":[{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}],
  "outputs":   [{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}],
  "outcomes":  [{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}]
}}

Rules:
- Extract only components explicitly stated or strongly implied in the document
- sourceQuote: a short PARAPHRASE (max 80 chars) of the supporting passage in your own words — do not copy text verbatim from the document
- Leave targetBenchmark and verificationSource as "" if not found in the document
- All string values must be valid JSON: escape any double quotes, backslashes, or line breaks within text
- Return ONLY the JSON object"""

    if req.document_base64:
        data = ai.generate_json_with_file(prompt, req.document_mime_type, req.document_base64)
    else:
        full_prompt = prompt + f"\n\nDocument text:\n{req.document_text}"
        data = ai.generate_json(full_prompt)

    return {"success": True, "data": data}


# ── Endpoint 7: Timeline Generation ───────────────────────────────────────────
@app.post("/api/ai/generate-timeline")
async def generate_timeline(req: GenerateTimelineRequest):
    components_text = "\n".join(
        f"- [{c.type}] {c.description}" + (f" (benchmark: {c.targetBenchmark})" if c.targetBenchmark else "")
        for c in req.components
    )

    prompt = f"""You are a senior Canadian government programme manager creating a realistic project timeline.

Project: {req.project_name}
Mandate: {req.mandate}

Logic Model Components:
{components_text}

Create a realistic project timeline. Weeks are relative to project start (Week 1 = start).

Return ONLY a valid JSON object — no markdown, no explanation:
{{
  "total_weeks": 52,
  "phases": [
    {{"name": "Foundation",      "start_week": 1,  "end_week": 12, "color": "#1d4ed8"}},
    {{"name": "Implementation",  "start_week": 13, "end_week": 40, "color": "#00c2ff"}},
    {{"name": "Evaluation",      "start_week": 41, "end_week": 52, "color": "#10b981"}}
  ],
  "items": [
    {{
      "component_type": "Input",
      "description":   "...",
      "start_week":    1,
      "end_week":      4,
      "phase":         "Foundation",
      "is_milestone":  false,
      "depends_on":    null,
      "rationale":     "one sentence explaining this timing"
    }}
  ],
  "critical_path_indices": [0, 2],
  "summary": "2-3 sentence plain-English explanation of the recommended timeline"
}}

Rules:
- Inputs always start at Week 1
- Activities follow Inputs; sequence them logically
- Outputs are milestones at the end of their producing Activities (is_milestone: true)
- Outcomes sit in the final third of the timeline
- For DRIPA Alignment or Self-Government Transition, allow 12-24 months minimum for negotiation activities
- Return ONLY the JSON object"""

    data = ai.generate_json(prompt)
    return {"success": True, "timeline": data}


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": "gemini-1.5-flash",
        "gemini_ready": ai.is_ready(),
    }


# ── Serve static frontend ──────────────────────────────────────────────────────
# Cache-Control: no-cache on the HTML shell ensures browsers always revalidate
# with the server after a deploy, instead of serving a stale cached copy of
# app.html (which embeds all of Keystone's JS inline). Without this, deployed
# frontend fixes can silently fail to take effect for users with an open tab
# or a cached page.
_NO_CACHE_HEADERS = {"Cache-Control": "no-cache, must-revalidate"}

@app.get("/")
async def serve_index():
    return FileResponse("index.html", headers=_NO_CACHE_HEADERS)

@app.get("/app.html")
async def serve_app():
    return FileResponse("app.html", headers=_NO_CACHE_HEADERS)

app.mount("/", StaticFiles(directory=".", html=True), name="static")
