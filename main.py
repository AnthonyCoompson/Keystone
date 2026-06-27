"""
Keystone — Policy Logic Diagnostic Tool
FastAPI backend — routes all AI work through ai_processor.py
© 2026 Anthony Coompson. All rights reserved.
"""

import logging
from typing import List, Optional, Any

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import ai_processor as ai
import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("keystone.main")

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Keystone AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    db.init_db()


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

class CrossRefComponent(BaseModel):
    type: str = ""
    description: str = ""
    targetBenchmark: str = ""
    verificationSource: str = ""

class CrossReferenceComponentsRequest(BaseModel):
    project_name: str = ""
    mandate: str = "Service Delivery"
    extracted_components: List[CrossRefComponent] = []
    existing_components: List[CrossRefComponent] = []

class TimelineComponent(BaseModel):
    type: str = ""
    description: str = ""
    targetBenchmark: str = ""

class GenerateTimelineRequest(BaseModel):
    project_name: str
    mandate: str
    components: List[TimelineComponent] = []

class TBComponentDetail(BaseModel):
    type: str = ""
    description: str = ""
    targetBenchmark: str = ""
    verificationSource: str = ""
    timeframe: Optional[str] = None
    baseline: Optional[str] = None
    responsibleParty: Optional[str] = None

class GenerateTBSubmissionRequest(BaseModel):
    project_name: str
    department: str
    mandate: str
    components: List[TBComponentDetail] = []

class CreateProjectFromDocumentRequest(BaseModel):
    document_text: str = ""
    document_base64: str = ""
    document_mime_type: str = "application/pdf"
    document_name: str = ""

class AssistantChatMessage(BaseModel):
    role: str = "user"   # "user" | "assistant"
    content: str = ""

class AssistantProjectContext(BaseModel):
    name: str = ""
    department: str = ""
    mandate: str = ""
    health_score: int = 0
    components: List[ComponentDetail] = []
    audit_findings: List[AuditFinding] = []

class AssistantChatRequest(BaseModel):
    message: str
    history: List[AssistantChatMessage] = []
    project: AssistantProjectContext | None = None


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

    data = ai.generate_json_large(prompt)
    return {"success": True, "data": data}


# ── Mandate-Aware Narrative Calibration ────────────────────────────────────────
# The AI Diagnostic Narrative used a single generic system prompt regardless
# of mandate, which produced technically-correct but contextually-thin
# writing — a DRIPA framework and a Service Delivery programme don't share
# the same accountability lens, and a narrative that doesn't speak in the
# right register reads as generic to the senior official it's meant for.
# Mirrors the frontend's MANDATE_CALIBRATION pattern (app.html) so the same
# logical model (mandate shapes evaluation) applies on both the scoring side
# and the narrative-writing side.
MANDATE_NARRATIVE_REGISTER = {
    "DRIPA Alignment": (
        "This is a DRIPA Section 7 / UNDRIP-aligned initiative. Foreground reconciliation "
        "obligations and the Province's statutory duty under DRIPA to act consistently with "
        "UNDRIP. Where data, tracking, or verification gaps appear, frame them specifically as "
        "OCAP compliance considerations — note whether verification sources are Nation-controlled "
        "or rely solely on provincial reporting systems, since that distinction matters for "
        "Indigenous data sovereignty. Where relevant, note Section 35 constitutional rights "
        "implications of jurisdictional or governance gaps. Avoid generic 'stakeholder engagement' "
        "language — use the language of joint decision-making, consent, and Nation-to-Nation "
        "relationship-building that DRIPA contexts require."
    ),
    "Self-Government Transition": (
        "This is a jurisdiction or governance transfer initiative. Foreground reconciliation "
        "obligations and the durability of the governance structure being built — gaps in this "
        "context aren't just programme risk, they're risk to the credibility of a jurisdictional "
        "transfer that the Nation and the Province both need to be able to defend. Where "
        "verification or data tracking gaps appear, frame them as OCAP compliance and Indigenous "
        "data sovereignty considerations. Note Section 35 implications where governance or "
        "jurisdictional authority is ambiguous or under-evidenced."
    ),
    "Service Delivery": (
        "This is a service delivery initiative (health, education, or social programme). "
        "Foreground programme continuity — whether the activities and resourcing described can "
        "sustain delivery past the current fiscal cycle — and outcome equity: whether the stated "
        "outcomes and their benchmarks would actually be felt evenly across the populations this "
        "programme is meant to serve, or whether gaps in the logic chain risk concentrating "
        "benefit in easier-to-reach groups. Avoid jurisdictional or reconciliation framing unless "
        "the components themselves raise it."
    ),
    "Economic Development": (
        "This is an economic development initiative. Foreground benefit-sharing — whether the "
        "logic model demonstrates that economic gains are structured to flow to the communities "
        "or Nations involved, not just to government or third-party proponents — and land-use "
        "revenue structures where relevant. Where verification gaps appear on financial or "
        "revenue-related benchmarks, note the audit and procurement-transparency stakes "
        "specifically, since economic development submissions face heightened scrutiny on exactly "
        "this point."
    ),
}

_DEFAULT_NARRATIVE_REGISTER = (
    "Use a general programme evaluation lens — assess structural integrity, accountability, and "
    "evaluability without assuming a specific policy register."
)

def _narrative_register_for(mandate: str) -> str:
    return MANDATE_NARRATIVE_REGISTER.get(mandate, _DEFAULT_NARRATIVE_REGISTER)


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
    register = _narrative_register_for(req.mandate)

    prompt = f"""You are a senior policy evaluation advisor writing for a Deputy Minister audience.

Project: {req.project_name}
Department: {req.department}
Mandate: {req.mandate}
Health Score: {req.health_score}/100

Mandate-specific framing for this narrative:
{register}

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
- Timeframe_Mismatch: short-term outcome with high-leverage activities that need more than a year, OR a long-term outcome with no intermediate deliverable

Write a 2-3 paragraph plain-English diagnostic narrative:
1. One-sentence overall assessment of the logic model's structural integrity
2. What the specific risk flags mean in the context of THIS project, applying the mandate-specific framing above where the findings make it relevant (not generic definitions, and don't force the framing onto findings it doesn't actually apply to)
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
        data = ai.generate_json_large(full_prompt)

    return {"success": True, "data": data}


# ── Endpoint 6b: Cross-Reference Extracted Components ──────────────────────────
# Called after Document Analysis extracts components from an uploaded
# document, IF a project is currently active. Compares the newly-extracted
# components against the project's existing ones and flags likely
# duplicates or contradictions BEFORE the analyst imports them — catching
# near-duplicates at the point of import rather than relying on Rule G
# (Duplicate_Component) to notice after the fact, and catching outright
# contradictions that no structural audit rule currently checks for at all
# (e.g. an extracted activity that describes doing the opposite of an
# existing outcome).
@app.post("/api/ai/cross-reference-components")
async def cross_reference_components(req: CrossReferenceComponentsRequest):
    if not req.existing_components or not req.extracted_components:
        # Nothing to compare against, or nothing new to check — return an
        # empty result rather than spending a Gemini call on a no-op.
        return {"success": True, "flags": []}

    def fmt(comps):
        return "\n".join(f"  [{i}] [{c.type}] {c.description}" for i, c in enumerate(comps)) or "  (none)"

    prompt = f"""You are an expert Canadian government policy analyst reviewing a logic model for
internal consistency before components from a newly-uploaded document are imported.

Project: {req.project_name or "Untitled"}
Mandate: {req.mandate}

EXISTING components already in the project's logic model:
{fmt(req.existing_components)}

NEWLY EXTRACTED components from the uploaded document, being considered for import:
{fmt(req.extracted_components)}

Compare the newly extracted components against the existing ones and identify only the
SIGNIFICANT issues an analyst should see before importing — do not flag minor wording
differences or components that are simply related but distinct.

Return ONLY a valid JSON array — no markdown, no explanation. Empty array if nothing significant:
[
  {{
    "extracted_index": 0,
    "extracted_description": "the new component's description, copied exactly",
    "issue_type": "duplicate" | "contradiction",
    "existing_index": 2,
    "existing_description": "the existing component's description, copied exactly",
    "explanation": "one sentence: why this is a likely duplicate, or specifically how it contradicts the existing component"
  }}
]

Rules:
- "duplicate": the new component describes substantively the same resource, action, or deliverable as an existing one, even if worded differently
- "contradiction": the new component states or implies something that conflicts with an existing component (e.g. a new activity claims to defer or replace something an existing output already claims was completed; a new outcome claims a different jurisdictional or governance outcome than an existing one)
- Only flag genuine duplicates or contradictions — most newly extracted components will be neither and should not appear in the output at all
- extracted_index and existing_index must match the bracketed [n] index shown above for that component
- Return ONLY the JSON array"""

    data = ai.generate_json(prompt)
    # Defensive: Gemini should return a list per the prompt, but guard
    # against a malformed/wrapped response so the frontend never crashes
    # trying to .map() over something unexpected.
    flags = data if isinstance(data, list) else data.get("flags", []) if isinstance(data, dict) else []
    return {"success": True, "flags": flags}


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

    data = ai.generate_json_large(prompt)
    return {"success": True, "timeline": data}


# ── Endpoint 7b: Treasury Board Performance Measurement Framework ─────────────
# Generates the mechanical-but-time-consuming "Performance Measurement
# Framework" table that Treasury Board submissions require: outcomes mapped
# to indicators, baselines, targets, and data sources, in roughly the
# structure TBS templates expect. This is exactly the kind of formatting-
# heavy, low-creativity drafting task that consumes analyst hours without
# requiring much judgment once the logic model itself is sound — Gemini
# handles the mechanical transformation well.
@app.post("/api/ai/generate-tb-submission")
async def generate_tb_submission(req: GenerateTBSubmissionRequest):
    outcomes = [c for c in req.components if c.type == "Outcome"]
    outputs = [c for c in req.components if c.type == "Output"]
    activities = [c for c in req.components if c.type == "Activity"]
    inputs = [c for c in req.components if c.type == "Input"]

    if not outcomes:
        raise HTTPException(
            status_code=400,
            detail="At least one Outcome is required to generate a Performance Measurement Framework.",
        )

    def fmt(comps, label):
        if not comps:
            return f"  (no {label} defined)"
        lines = []
        for c in comps:
            line = f"  - {c.description}"
            if c.targetBenchmark: line += f" | benchmark: {c.targetBenchmark}"
            if c.verificationSource: line += f" | verification: {c.verificationSource}"
            if c.timeframe: line += f" | timeframe: {c.timeframe}"
            if c.baseline: line += f" | baseline: {c.baseline}"
            if c.responsibleParty: line += f" | responsible party: {c.responsibleParty}"
            lines.append(line)
        return "\n".join(lines)

    components_text = (
        f"INPUTS:\n{fmt(inputs,'inputs')}\n\n"
        f"ACTIVITIES:\n{fmt(activities,'activities')}\n\n"
        f"OUTPUTS:\n{fmt(outputs,'outputs')}\n\n"
        f"OUTCOMES:\n{fmt(outcomes,'outcomes')}"
    )

    prompt = f"""You are a Canadian federal/provincial government policy analyst drafting the Performance
Measurement Framework section of a Treasury Board submission, in the format Treasury Board
Secretariat (TBS) expects: a structured table mapping each outcome to its performance
indicator(s), baseline, target, data source, and reporting frequency.

Project: {req.project_name}
Department: {req.department}
Mandate: {req.mandate}

Logic Model:
{components_text}

Return ONLY a valid JSON object — no markdown, no explanation:
{{
  "framework_title": "Performance Measurement Framework — {req.project_name}",
  "immediate_outcomes": [
    {{
      "outcome": "...",
      "indicator": "a specific, measurable performance indicator for this outcome",
      "baseline": "current state — use the project's stated baseline if provided, otherwise state a realistic placeholder and mark it '(TO BE CONFIRMED)'",
      "target": "a specific numeric or qualitative target with a date",
      "data_source": "named verification mechanism",
      "reporting_frequency": "Annual | Semi-annual | Quarterly"
    }}
  ],
  "intermediate_outcomes": [ /* same shape, for medium-term (1-3yr) outcomes */ ],
  "ultimate_outcomes": [ /* same shape, for long-term (3yr+) outcomes */ ],
  "narrative_summary": "2-3 sentence plain-English summary of how this performance measurement approach demonstrates accountability, written for inclusion at the top of the TBS section",
  "data_gaps": ["explicit list of any outcomes where the logic model didn't provide a baseline, target, or verification source — name the outcome and what's missing, so the analyst knows what to fill in before submission"]
}}

Rules:
- Classify each Outcome into immediate_outcomes (short-term/<1yr), intermediate_outcomes (medium-term/1-3yr), or ultimate_outcomes (long-term/3yr+) based on its stated timeframe; if no timeframe was given, use your judgment based on the outcome's description and place it in the most defensible category
- Every indicator must be SPECIFIC and MEASURABLE — never vague language like "improved" or "increased" without a quantity or rate
- If the logic model already provided a baseline, target (from targetBenchmark), or data source (from verificationSource) for an outcome, use that exact information rather than inventing new figures
- If information is missing, do not silently fabricate precise numbers — use a clearly-marked placeholder and also list it in data_gaps
- For DRIPA Alignment or Self-Government Transition mandates, data sources should note Nation-controlled or OCAP-compliant mechanisms where the logic model's verification sources support that
- Return ONLY the JSON object"""

    data = ai.generate_json_large(prompt)
    return {"success": True, "submission": data}


# ── Endpoint 8: Create Project From Document ──────────────────────────────────
# Combines project-field extraction (name/department/description/mandate) and
# logic model component extraction into a single Gemini call, so a user can
# drop a briefing note / operational plan into "New Project" and get both the
# project shell AND its starting components in one round trip.
@app.post("/api/ai/create-project-from-document")
async def create_project_from_document(req: CreateProjectFromDocumentRequest):
    prompt = f"""You are an expert Canadian government policy analyst specialising in logic models.

A policy document has been provided (e.g. a briefing note, operational plan, or agreement).
Document name: {req.document_name or "Untitled"}

From this document, do TWO things:

1. Extract structured PROJECT fields describing the overall initiative.
2. Extract a logic model: Inputs, Activities, Outputs, and Outcomes explicitly stated or strongly implied.

Return ONLY a valid JSON object — no markdown, no explanation:
{{
  "project": {{
    "name":        "...",
    "department":  "...",
    "description": "...",
    "mandate":     "..."
  }},
  "components": {{
    "inputs":    [{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}],
    "activities":[{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}],
    "outputs":   [{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}],
    "outcomes":  [{{"description":"...","targetBenchmark":"...","verificationSource":"...","sourceQuote":"..."}}]
  }}
}}

Rules:
- project.name: formal title-case project name
- project.department: the most likely BC or federal government department responsible
- project.description: 1-2 sentences in formal policy language
- project.mandate: MUST be exactly one of:
    "DRIPA Alignment" | "Self-Government Transition" | "Service Delivery" | "Economic Development"
  Use "DRIPA Alignment" for joint decision-making or UNDRIP implementation.
  Use "Self-Government Transition" for jurisdiction or governance transfer.
  Use "Service Delivery" for health, education, or social programmes.
  Use "Economic Development" for economic opportunities or land-use revenue.
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

    project = data.get("project", {}) if isinstance(data, dict) else {}
    components = data.get("components", {}) if isinstance(data, dict) else {}

    valid_mandates = ["DRIPA Alignment", "Self-Government Transition", "Service Delivery", "Economic Development"]
    if project.get("mandate") not in valid_mandates:
        project["mandate"] = "DRIPA Alignment"

    return {"success": True, "project": project, "components": components}


# ── Endpoint 9: AI Assistant Chat ──────────────────────────────────────────────
# Embedded assistant available across every tab. When a project is active, its
# components, mandate, health score, and current audit findings are passed in
# as context so the assistant can answer project-specific questions
# ("why is my score low?", "what should I fix first?") as well as general
# Keystone / policy logic questions.
@app.post("/api/ai/assistant-chat")
async def assistant_chat(req: AssistantChatRequest):
    context_text = "No project is currently open."
    if req.project and (req.project.name or req.project.components):
        p = req.project
        comp_lines = "\n".join(
            f"  - [{c.type}] {c.description}"
            + (f" (benchmark: {c.targetBenchmark})" if c.targetBenchmark else "")
            + (f" (verification: {c.verificationSource})" if c.verificationSource else " (NO verification source)")
            for c in p.components
        ) or "  (no components yet)"
        finding_lines = "\n".join(
            f"  - [{f.riskLevel} / {f.errorType}] {f.message}"
            for f in p.audit_findings
        ) or "  (no risk flags)"
        context_text = f"""The analyst currently has this project open:
Project: {p.name}
Department: {p.department}
Mandate: {p.mandate}
Health Score: {p.health_score}/100

Logic Model Components:
{comp_lines}

Current Audit Findings:
{finding_lines}"""

    history_text = "\n".join(
        f"{'Analyst' if m.role == 'user' else 'Keystone Assistant'}: {m.content}"
        for m in req.history[-10:]  # cap context window
    )

    prompt = f"""You are the Keystone Assistant — an embedded helper inside Keystone, a policy logic
diagnostic tool for Canadian government policy analysts (BC and federal). You help analysts
build, audit, and improve programme logic models (Input → Activity → Output → Outcome) and
understand Keystone's audit rules: Dead End, Miracle Leap, Blind Spot, Circular Logic,
Orphaned Input, Scale Mismatch, Duplicate Component, and Timeframe Mismatch.

{context_text}

Conversation so far:
{history_text}

Analyst's new message: "{req.message}"

Respond directly and helpfully in 1-3 short paragraphs (or a brief list if listing concrete
steps). If the analyst asks about their current project, refer to the specific components and
findings above by name — do not give generic advice when specific context is available. If no
project is open and the question requires one, say so and suggest opening or creating a
project. Keep a professional, direct tone. Do not use technical error-type names verbatim
(e.g. say "Blind Spot" only if explaining what it means) — but DO use them when the analyst
has used them first. Return ONLY the response text — no markdown headers, no preamble."""

    text = ai.generate_text(prompt)
    return {"success": True, "reply": text.strip()}


# ── Sync — Backend Persistence ──────────────────────────────────────────────
# Replaces localStorage as the source of truth. The frontend's setData() now
# fires a debounced push() after every write, and pull() runs once on app
# load to hydrate localStorage from the server (so a cleared browser, a new
# device, or a shared link all see the same data).
#
# Scoping: each browser gets a stable random device_id (generated once,
# persisted in localStorage itself, sent as the X-Device-Id header). This
# preserves today's "one browser, one set of projects" behaviour while
# giving every project a durable home outside the browser. A future
# sharing feature can re-scope specific projects to a shared workspace id
# without changing this endpoint shape.

class SyncProject(BaseModel):
    id: str
    name: str = ""
    department: str = ""
    description: str = ""
    mandate: str = ""
    createdAt: Optional[str] = None
    timeline: Optional[Any] = None

class SyncComponent(BaseModel):
    id: str
    projectId: str
    type: str = ""
    description: str = ""
    targetBenchmark: str = ""
    verificationSource: str = ""
    timeframe: Optional[str] = None
    # Explicit relationship links (see app.html hasExplicitLinks/buildLogicModelGraph).
    # Optional/nullable because most components never set these — only
    # Activities and Outputs carry link pickers in the UI.
    linkedInputIds: Optional[List[str]] = None
    linkedOutputIds: Optional[List[str]] = None
    linkedOutcomeIds: Optional[List[str]] = None
    # Completeness rubric extra fields (see computeCompletenessScores in
    # app.html) — baseline only meaningful for Outcomes, responsibleParty
    # only meaningful for Outputs.
    baseline: Optional[str] = None
    responsibleParty: Optional[str] = None

class SyncRuleSettings(BaseModel):
    projectId: str
    completeness: dict = {}
    timeframeCoherence: dict = {}

class SyncProjectVersion(BaseModel):
    id: str
    projectId: str
    label: str = ""
    timestamp: Any
    mandate: str = ""
    score: int = 0
    components: List[Any] = []
    findings: List[Any] = []

class SyncAuditEntry(BaseModel):
    id: str
    projectId: str
    riskLevel: str = ""
    errorType: str = ""
    message: str = ""
    componentId: Optional[str] = None

class SyncScoreHistoryEntry(BaseModel):
    projectId: str
    score: int
    ts: Any  # epoch ms, sent as number from JS

class SyncDocAnalysisEntry(BaseModel):
    id: str
    fileName: str = ""
    mandate: str = ""
    timestamp: Any
    components: List[Any] = []

class SyncPushRequest(BaseModel):
    projects: List[SyncProject] = []
    components: List[SyncComponent] = []
    auditLog: List[SyncAuditEntry] = []
    scoreHistory: List[SyncScoreHistoryEntry] = []
    docAnalysisHistory: List[SyncDocAnalysisEntry] = []
    projectVersions: List[SyncProjectVersion] = []
    ruleSettings: List[SyncRuleSettings] = []
    # ids the client deleted locally since the last push, so the server
    # mirrors deletions instead of only ever accumulating rows
    deletedProjectIds: List[str] = []
    deletedComponentIds: List[str] = []
    deletedDocAnalysisIds: List[str] = []
    deletedVersionIds: List[str] = []


def _require_device_id(x_device_id: Optional[str]) -> str:
    if not x_device_id or not x_device_id.strip():
        raise HTTPException(status_code=400, detail="Missing X-Device-Id header.")
    return x_device_id.strip()


@app.get("/api/sync/pull")
async def sync_pull(x_device_id: Optional[str] = Header(default=None)):
    device_id = _require_device_id(x_device_id)
    session = db.get_session()
    try:
        projects = session.query(db.Project).filter_by(device_id=device_id).all()
        components = session.query(db.Component).filter_by(device_id=device_id).all()
        audit_entries = session.query(db.AuditEntry).filter_by(device_id=device_id).all()
        score_history = session.query(db.ScoreHistoryEntry).filter_by(device_id=device_id).all()
        doc_history = session.query(db.DocAnalysisHistoryEntry).filter_by(device_id=device_id).all()
        versions = session.query(db.ProjectVersion).filter_by(device_id=device_id).all()
        rule_settings = session.query(db.RuleSettings).filter_by(device_id=device_id).all()

        return {
            "success": True,
            "projects": [
                {
                    "id": p.id, "name": p.name, "department": p.department,
                    "description": p.description, "mandate": p.mandate,
                    "createdAt": p.created_at, "timeline": p.timeline,
                }
                for p in projects
            ],
            "components": [
                {
                    "id": c.id, "projectId": c.project_id, "type": c.type,
                    "description": c.description, "targetBenchmark": c.target_benchmark,
                    "verificationSource": c.verification_source, "timeframe": c.timeframe,
                    "linkedInputIds": c.linked_input_ids, "linkedOutputIds": c.linked_output_ids,
                    "linkedOutcomeIds": c.linked_outcome_ids,
                    "baseline": c.baseline, "responsibleParty": c.responsible_party,
                }
                for c in components
            ],
            "auditLog": [
                {
                    "id": a.id, "projectId": a.project_id, "riskLevel": a.risk_level,
                    "errorType": a.error_type, "message": a.message, "componentId": a.component_id,
                }
                for a in audit_entries
            ],
            "scoreHistory": [
                {"projectId": s.project_id, "score": s.score, "ts": s.ts}
                for s in score_history
            ],
            "docAnalysisHistory": [
                {
                    "id": d.id, "fileName": d.file_name, "mandate": d.mandate,
                    "timestamp": d.timestamp, "components": d.components,
                }
                for d in doc_history
            ],
            "projectVersions": [
                {
                    "id": v.id, "projectId": v.project_id, "label": v.label,
                    "timestamp": v.timestamp, "mandate": v.mandate, "score": v.score,
                    "components": v.components, "findings": v.findings,
                }
                for v in versions
            ],
            "ruleSettings": [
                {
                    "projectId": r.project_id, "completeness": r.completeness,
                    "timeframeCoherence": r.timeframe_coherence,
                }
                for r in rule_settings
            ],
        }
    finally:
        session.close()


@app.post("/api/sync/push")
async def sync_push(req: SyncPushRequest, x_device_id: Optional[str] = Header(default=None)):
    device_id = _require_device_id(x_device_id)
    session = db.get_session()
    try:
        if req.projects:
            rows = [{
                "id": p.id, "device_id": device_id, "name": p.name, "department": p.department,
                "description": p.description, "mandate": p.mandate, "created_at": p.createdAt,
                "timeline": p.timeline,
            } for p in req.projects]
            db.upsert_rows(session, db.Project, rows)

        if req.components:
            rows = [{
                "id": c.id, "device_id": device_id, "project_id": c.projectId, "type": c.type,
                "description": c.description, "target_benchmark": c.targetBenchmark,
                "verification_source": c.verificationSource, "timeframe": c.timeframe,
                "linked_input_ids": c.linkedInputIds, "linked_output_ids": c.linkedOutputIds,
                "linked_outcome_ids": c.linkedOutcomeIds,
                "baseline": c.baseline, "responsible_party": c.responsibleParty,
            } for c in req.components]
            db.upsert_rows(session, db.Component, rows)

        if req.auditLog:
            rows = [{
                "id": a.id, "device_id": device_id, "project_id": a.projectId,
                "risk_level": a.riskLevel, "error_type": a.errorType, "message": a.message,
                "component_id": a.componentId,
            } for a in req.auditLog]
            db.upsert_rows(session, db.AuditEntry, rows)

        if req.docAnalysisHistory:
            rows = [{
                "id": d.id, "device_id": device_id, "file_name": d.fileName, "mandate": d.mandate,
                "timestamp": str(d.timestamp), "components": d.components,
            } for d in req.docAnalysisHistory]
            db.upsert_rows(session, db.DocAnalysisHistoryEntry, rows)

        if req.projectVersions:
            rows = [{
                "id": v.id, "device_id": device_id, "project_id": v.projectId, "label": v.label,
                "timestamp": str(v.timestamp), "mandate": v.mandate, "score": v.score,
                "components": v.components, "findings": v.findings,
            } for v in req.projectVersions]
            db.upsert_rows(session, db.ProjectVersion, rows)

        if req.ruleSettings:
            rows = [{
                "project_id": r.projectId, "device_id": device_id,
                "completeness": r.completeness, "timeframe_coherence": r.timeframeCoherence,
            } for r in req.ruleSettings]
            db.upsert_rows(session, db.RuleSettings, rows)

        # Score history is append-only and has no client-assigned id, so we
        # simply insert any rows not already represented (cheap dedupe on
        # project_id + ts, which is effectively unique per save event).
        for s in req.scoreHistory:
            exists = session.query(db.ScoreHistoryEntry).filter_by(
                device_id=device_id, project_id=s.projectId, ts=str(s.ts)
            ).first()
            if not exists:
                session.add(db.ScoreHistoryEntry(
                    device_id=device_id, project_id=s.projectId, score=s.score, ts=str(s.ts)
                ))

        # Mirror deletions
        if req.deletedProjectIds:
            session.query(db.Project).filter(
                db.Project.device_id == device_id, db.Project.id.in_(req.deletedProjectIds)
            ).delete(synchronize_session=False)
            session.query(db.Component).filter(
                db.Component.device_id == device_id, db.Component.project_id.in_(req.deletedProjectIds)
            ).delete(synchronize_session=False)
            session.query(db.AuditEntry).filter(
                db.AuditEntry.device_id == device_id, db.AuditEntry.project_id.in_(req.deletedProjectIds)
            ).delete(synchronize_session=False)
            session.query(db.ScoreHistoryEntry).filter(
                db.ScoreHistoryEntry.device_id == device_id, db.ScoreHistoryEntry.project_id.in_(req.deletedProjectIds)
            ).delete(synchronize_session=False)
            session.query(db.ProjectVersion).filter(
                db.ProjectVersion.device_id == device_id, db.ProjectVersion.project_id.in_(req.deletedProjectIds)
            ).delete(synchronize_session=False)
            session.query(db.RuleSettings).filter(
                db.RuleSettings.device_id == device_id, db.RuleSettings.project_id.in_(req.deletedProjectIds)
            ).delete(synchronize_session=False)

        if req.deletedComponentIds:
            session.query(db.Component).filter(
                db.Component.device_id == device_id, db.Component.id.in_(req.deletedComponentIds)
            ).delete(synchronize_session=False)

        if req.deletedDocAnalysisIds:
            session.query(db.DocAnalysisHistoryEntry).filter(
                db.DocAnalysisHistoryEntry.device_id == device_id,
                db.DocAnalysisHistoryEntry.id.in_(req.deletedDocAnalysisIds)
            ).delete(synchronize_session=False)

        if req.deletedVersionIds:
            session.query(db.ProjectVersion).filter(
                db.ProjectVersion.device_id == device_id,
                db.ProjectVersion.id.in_(req.deletedVersionIds)
            ).delete(synchronize_session=False)

        session.commit()
        return {"success": True}
    except Exception as exc:
        session.rollback()
        logger.error(f"Sync push failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(exc)}")
    finally:
        session.close()


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    db_ready = True
    try:
        session = db.get_session()
        session.execute(db.Project.__table__.select().limit(1))
        session.close()
    except Exception as exc:
        logger.warning(f"Health check DB probe failed: {exc}")
        db_ready = False
    return {
        "status": "ok",
        "model": ai._MODEL,
        "gemini_ready": ai.is_ready(),
        "db_ready": db_ready,
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
