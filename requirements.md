# Requirements Document

## Introduction

Keystone is a single-file, browser-based diagnostic tool for Policy Analysts to stress-test causal logic in policy frameworks. It enables analysts to build logic models using the Input → Activity → Output → Outcome chain, automatically audits those models for structural failures (Dead Ends, Miracle Leaps, and Blind Spots), and generates printable executive briefings. All data is persisted in localStorage with no backend required.

## Glossary

- **Keystone**: The application described in this document — a policy logic model diagnostic tool.
- **Policy_Analyst**: The primary user role; a professional who designs and evaluates government policy frameworks.
- **Logic_Model**: A structured representation of a programme's causal chain: Inputs → Activities → Outputs → Outcomes.
- **Framework_Component**: A single node in a Logic_Model, typed as Input, Activity, Output, or Outcome.
- **Project**: A named policy evaluation effort containing one or more Framework_Components.
- **Audit_Engine**: The rule-based subsystem that analyses Framework_Components and produces Audit_Log entries.
- **Audit_Log**: The persisted collection of risk findings produced by the Audit_Engine for a given Project.
- **Health_Score**: A 0–100 integer derived from Audit_Log risk counts; formula: `Math.max(0, 100 - (highCount * 20) - (mediumCount * 8))`.
- **Dead_End**: An Audit_Engine error type indicating an Activity with no mapped Output or Outcome.
- **Miracle_Leap**: An Audit_Engine error type indicating a major systemic Outcome unsupported by substantive Activities.
- **Blind_Spot**: An Audit_Engine error type indicating an Output or Outcome with no defined verification source.
- **Executive_Briefing**: A printable HTML report summarising a Project's Logic_Model and Audit_Log findings.
- **Active_Project**: The Project currently selected for editing and auditing in the New Evaluation view.
- **DRIPA**: Declaration on the Rights of Indigenous Peoples Act (BC), the legislative mandate context for one mandate classification.
- **OCAP**: Ownership, Control, Access, and Possession — Indigenous data sovereignty principles referenced in methodology content.
- **localStorage**: The browser-native key-value store used for all data persistence.

---

## Requirements

### Requirement 1: Single-File Delivery and Technology Constraints

**User Story:** As a Policy_Analyst, I want to open Keystone by simply opening a single HTML file in a browser, so that I can use the tool without installing software or configuring a server.

#### Acceptance Criteria

1. THE Keystone SHALL be delivered as a single `index.html` file containing all HTML, CSS, and JavaScript inline.
2. THE Keystone SHALL import external libraries exclusively from `https://cdnjs.cloudflare.com` via CDN `<script>` or `<link>` tags.
3. THE Keystone SHALL import the IBM Plex Sans typeface from Google Fonts.
4. THE Keystone SHALL require no build step, no Node.js runtime, and no backend server to function.
5. THE Keystone SHALL persist all application state exclusively in `localStorage` under the keys `ks_projects`, `ks_components`, and `ks_audit_log`.

---

### Requirement 2: Visual Design System

**User Story:** As a Policy_Analyst, I want a consistent, professional visual design, so that the tool feels credible and is easy to read during high-stakes policy work.

#### Acceptance Criteria

1. THE Keystone SHALL define and apply the following CSS custom properties: `--slate: #2d3f5e`, `--slate-dark: #1a2740`, `--slate-light: #3d5278`, `--charcoal: #2c2c2c`, `--white: #ffffff`, `--bg: #f4f6f9`, `--border: #dde3ed`, `--text: #1a2740`, `--muted: #6b7a99`, `--amber: #f59e0b`, `--red: #dc2626`, `--green: #16a34a`, `--cyan: #0ea5e9`.
2. THE Keystone SHALL render as a fixed-height, full-viewport application with no page-level scroll.
3. THE Keystone SHALL use CSS Grid for the outer application shell layout.
4. WHEN the viewport width is less than 768px, THE Keystone SHALL collapse to a single-column layout with a top navigation bar replacing the sidebar.
5. WHEN the viewport width is less than 768px, THE Keystone SHALL display icon-only navigation items in the top bar.
6. WHEN a view transition occurs, THE Keystone SHALL animate the incoming view from opacity 0 to opacity 1 over 200ms using a CSS transition.

---

### Requirement 3: Application Shell and Navigation

**User Story:** As a Policy_Analyst, I want a persistent sidebar with clear navigation, so that I can move between the Projects list, the Evaluation builder, and the Methodology reference without losing context.

#### Acceptance Criteria

1. THE Keystone SHALL render an `#app-shell` element using a CSS Grid layout with a 220px sidebar column and a `1fr` main content column.
2. THE Keystone SHALL render a `#sidebar` containing a brand area, a `nav#sidebar-nav`, and an Active_Project indicator.
3. THE brand area SHALL display a geometric diamond SVG icon and the wordmark "Keystone" in IBM Plex Sans at font-weight 600.
4. THE `nav#sidebar-nav` SHALL contain exactly three navigation items: "Active Projects" (`data-view="projects"`), "New Evaluation" (`data-view="new-framework"`), and "Methodology" (`data-view="methodology"`).
5. WHEN a nav item is clicked, THE Keystone SHALL hide all view panels and show only the view panel matching the clicked item's `data-view` attribute.
6. WHEN a nav item is active, THE Keystone SHALL apply a left border accent in `--cyan` and a background tint to that nav item.
7. THE Active_Project indicator SHALL display the name of the Active_Project, or the text "No project selected" in `--muted` colour when no Active_Project is set.
8. WHEN a nav item is hovered, THE Keystone SHALL display a tooltip via the `title` attribute.
9. THE Keystone SHALL render three view panels: `#view-projects`, `#view-new-framework`, and `#view-methodology`.
10. THE `#view-new-framework` SHALL be the default active view on application load.

---

### Requirement 4: Data Models and Storage Helpers

**User Story:** As a Policy_Analyst, I want my projects and components to be saved automatically, so that my work persists between browser sessions without any manual save action.

#### Acceptance Criteria

1. THE Keystone SHALL store Project records in `localStorage` under the key `ks_projects` as a JSON array, where each Project has the fields: `id` (string), `name` (string), `department` (string), `description` (string), `mandate` (string), `createdAt` (string ISO-8601).
2. THE `mandate` field of a Project SHALL accept exactly one of the values: `"DRIPA Alignment"`, `"Self-Government Transition"`, `"Service Delivery"`, `"Economic Development"`.
3. THE Keystone SHALL store Framework_Component records in `localStorage` under the key `ks_components` as a JSON array, where each Framework_Component has the fields: `id` (string), `projectId` (string), `type` (string), `description` (string), `targetBenchmark` (string), `verificationSource` (string).
4. THE `type` field of a Framework_Component SHALL accept exactly one of the values: `"Input"`, `"Activity"`, `"Output"`, `"Outcome"`.
5. THE Keystone SHALL store Audit_Log records in `localStorage` under the key `ks_audit_log` as a JSON array, where each Audit_Log record has the fields: `id` (string), `projectId` (string), `riskLevel` (string), `errorType` (string), `message` (string), `componentId` (string).
6. THE `riskLevel` field of an Audit_Log record SHALL be one of: `"Low"`, `"Medium"`, `"High"`.
7. THE `errorType` field of an Audit_Log record SHALL be one of: `"Dead_End"`, `"Miracle_Leap"`, `"Blind_Spot"`.
8. THE Keystone SHALL expose helper functions `getData(key)`, `setData(key, array)`, and `generateId()` for all localStorage read/write operations.

---

### Requirement 5: Active Projects View

**User Story:** As a Policy_Analyst, I want to see all my projects at a glance and manage them from a single screen, so that I can quickly switch between evaluations or clean up completed work.

#### Acceptance Criteria

1. WHEN the "Active Projects" nav item is clicked, THE Keystone SHALL render a card grid of all Project records from `ks_projects`.
2. THE Project card SHALL display: project name in bold `--slate` colour, department in `--muted` small text, a mandate badge as a coloured pill, a count of associated Framework_Components, and a risk summary showing High and Medium flag counts from `ks_audit_log`.
3. THE mandate badge colour SHALL be: amber for "DRIPA Alignment", purple (`#7c3aed`) for "Self-Government Transition", `--slate` for "Service Delivery", `--green` for "Economic Development".
4. THE Project card SHALL contain an "Open" button and a "Delete" button.
5. WHEN the "Open" button is clicked, THE Keystone SHALL set the clicked Project as the Active_Project and navigate to the New Evaluation view.
6. WHEN the "Delete" button is clicked, THE Keystone SHALL display a `window.confirm()` dialog with a descriptive message before proceeding.
7. WHEN deletion is confirmed, THE Keystone SHALL remove the Project record, all associated Framework_Component records, and all associated Audit_Log records from `localStorage`.
8. THE Active Projects view SHALL display a "+ New Project" button at the top of the view.
9. WHEN the "+ New Project" button is clicked, THE Keystone SHALL open a modal form with fields: Name (text, required), Department (text, required), Description (textarea), Mandate (dropdown with the four mandate values).
10. WHEN the new project form is submitted with valid data, THE Keystone SHALL create a new Project record, set it as the Active_Project, close the modal, and navigate to the New Evaluation view.
11. WHEN no Project records exist, THE Keystone SHALL display an empty state message in the Active Projects view.

---

### Requirement 6: New Evaluation Framework View — Split Screen Layout

**User Story:** As a Policy_Analyst, I want a split-screen workspace where I build my logic model on the left and see live audit feedback on the right, so that I can iteratively improve my framework without switching screens.

#### Acceptance Criteria

1. THE `#view-new-framework` SHALL use a CSS Grid inner layout with a `1fr` left column (`#form-panel`) and a `380px` right column (`#audit-panel`).
2. THE `#form-panel` SHALL contain a multi-step wizard with four steps corresponding to the four Framework_Component types: Input, Activity, Output, Outcome.
3. THE `#form-panel` SHALL display a step indicator showing four horizontal steps labelled "Input", "Activity", "Output", "Outcome", with the current step highlighted.
4. THE step indicator steps SHALL be clickable to navigate directly to any step.
5. EACH wizard step SHALL display: a step title, a 2-sentence description of the component type, a required textarea for Description, a text input for Target Benchmark, and a text input for Verification/Data Source.
6. THE Verification/Data Source input SHALL display the placeholder text: "e.g., FNHA quarterly reporting, Treasury Board submission, community survey".
7. THE `#form-panel` SHALL display step-specific guidance text below the Description textarea as follows — Input: "Resources committed to this initiative. Include funding envelopes, FTEs, and legislative time."; Activity: "Actions taken using these inputs. Include engagement sessions, co-drafting processes, consultations."; Output: "Tangible deliverables produced. Include documents signed, sessions held, frameworks published."; Outcome: "Systemic changes achieved. Include jurisdictional recognition, governance shifts, data sovereignty gains."
8. THE `#form-panel` SHALL display an "Add Component" button on each step.
9. WHEN the "Add Component" button is clicked with an empty Description field, THE Keystone SHALL display inline red helper text below the Description field without using `alert()`.
10. WHEN the "Add Component" button is clicked with a valid Description, THE Keystone SHALL save the Framework_Component to `ks_components`, re-run the Audit_Engine for the Active_Project, and clear the form fields.
11. THE `#form-panel` SHALL display a scrollable list of all Framework_Components for the Active_Project, grouped by type, below the form.
12. EACH component list item SHALL display: the description truncated to 60 characters, a type badge, and a delete icon (×).
13. WHEN the delete icon is clicked on a component list item, THE Keystone SHALL remove the Framework_Component from `ks_components`, re-run the Audit_Engine, and re-render the component list.
14. THE `#form-panel` SHALL display "Previous" and "Next" navigation buttons to move between wizard steps.

---

### Requirement 7: Logic Auditor Panel

**User Story:** As a Policy_Analyst, I want a live audit panel that continuously evaluates my logic model, so that I can identify and fix structural weaknesses before submitting a policy framework.

#### Acceptance Criteria

1. THE `#audit-panel` SHALL display a "Logic Audit" header and a live timestamp showing "Last checked: X seconds ago".
2. THE timestamp SHALL update every 30 seconds via `setInterval`.
3. THE `#audit-panel` SHALL display the Health_Score as a CSS-only coloured circle gauge showing the integer value 0–100.
4. THE Health_Score circle SHALL be coloured green when the score is ≥ 70, amber when the score is 40–69, and red when the score is < 40.
5. THE `#audit-panel` SHALL display the text "N risks detected" below the Health_Score circle, where N is the total count of Audit_Log entries for the Active_Project.
6. THE `#audit-panel` SHALL display a scrollable Risk Feed of all Audit_Log entries for the Active_Project, sorted with High risk entries first.
7. EACH Risk Feed entry SHALL display: a coloured left border (red for High, amber for Medium, green for Low), the error type as a small all-caps label, the message text, and the associated component description truncated in muted text.
8. WHEN the Active_Project has no Audit_Log entries, THE `#audit-panel` SHALL display the empty state message: "✓ No logic gaps detected. Keep building your framework."
9. THE `#audit-panel` SHALL display a Component Coverage Summary with four stat boxes showing counts for Inputs, Activities, Outputs, and Outcomes.
10. WHEN any component type count in the Coverage Summary is 0, THE `#audit-panel` SHALL display a warning indicator for that type.

---

### Requirement 8: Audit Engine Rules

**User Story:** As a Policy_Analyst, I want the tool to automatically detect Dead Ends, Miracle Leaps, and Blind Spots in my logic model, so that I receive objective structural feedback without needing a peer reviewer.

#### Acceptance Criteria

1. WHEN `runAuditEngine(projectId)` is called, THE Audit_Engine SHALL clear all existing Audit_Log entries for the given `projectId` before evaluating new rules.
2. WHEN `runAuditEngine(projectId)` is called, THE Audit_Engine SHALL fetch all Framework_Components for the given `projectId` from `ks_components`.
3. THE Audit_Engine SHALL apply Rule A (Dead_End): FOR EACH Framework_Component where `type === "Activity"`, IF the project has zero Framework_Components of type "Output" AND zero Framework_Components of type "Outcome", THEN THE Audit_Engine SHALL create a High-risk Audit_Log entry with `errorType: "Dead_End"` and the message: "Dead End: You are allocating resources to activities with no mapped deliverables or systemic impact. Add at least one Output or Outcome to complete the logic chain."
4. THE Audit_Engine SHALL apply Rule B (Miracle_Leap): FOR EACH Framework_Component where `type === "Outcome"` whose description contains any of the keywords ["jurisdiction", "sovereignty", "self-government", "governance", "treaty", "title", "rights", "systemic", "transformational", "full authority"], IF all Activity-type Framework_Components for the project have descriptions containing only minor-activity keywords ["webinar", "workshop", "meeting", "email", "newsletter", "survey", "report drafted"] AND at least one Activity exists, THEN THE Audit_Engine SHALL create a Medium-risk Audit_Log entry with `errorType: "Miracle_Leap"` and the message: "Miracle Leap: Your stated activities appear structurally insufficient to achieve this systemic outcome. Consider adding high-leverage activities such as legislative drafting, formal negotiations, or co-governance body establishment."
5. THE Audit_Engine SHALL apply Rule C (Blind_Spot): FOR EACH Framework_Component where `type === "Output"` OR `type === "Outcome"`, AND FOR EACH Framework_Component where `type === "Activity"` AND `targetBenchmark` is non-empty, IF the `verificationSource` field is empty or contains only whitespace, THEN THE Audit_Engine SHALL create a Medium-risk Audit_Log entry with `errorType: "Blind_Spot"` and the message: `Blind Spot: "[component description truncated to 40 chars]" has no defined data source. Without a tracking mechanism, this benchmark cannot be evaluated or reported on.`
6. WHEN all rules have been evaluated, THE Audit_Engine SHALL save all new Audit_Log entries to `ks_audit_log` and re-render the `#audit-panel`.
7. THE Audit_Engine SHALL be invoked on every Framework_Component addition, every Framework_Component deletion, and on Active_Project load.

---

### Requirement 9: Executive Briefing Generation

**User Story:** As a Policy_Analyst, I want to generate a printable executive briefing from my completed logic model, so that I can share diagnostic findings with decision-makers without manual formatting.

#### Acceptance Criteria

1. THE `#audit-panel` SHALL display a "Generate Executive Briefing" button in its footer.
2. WHEN the Active_Project has fewer than 2 Framework_Components, THE "Generate Executive Briefing" button SHALL be hidden.
3. WHEN the "Generate Executive Briefing" button is clicked, THE Keystone SHALL generate an HTML string and open it in a new browser tab using `window.open()`.
4. THE Executive_Briefing SHALL include: the title "KEYSTONE DIAGNOSTIC REPORT", the project name and department, the generation date, the mandate classification, a Programme Logic Model section listing all Framework_Components grouped by type with description, targetBenchmark, and verificationSource, a Diagnostic Audit Findings section showing the Health_Score and all Audit_Log entries grouped by risk level, and a Recommendations section.
5. THE Recommendations section SHALL include the message "Ensure every every activity produces at least one measurable output." IF any Dead_End Audit_Log entries exist for the Active_Project.
6. THE Recommendations section SHALL include the message "Review the sufficiency of planned activities relative to stated systemic outcomes." IF any Miracle_Leap Audit_Log entries exist for the Active_Project.
7. THE Recommendations section SHALL include the message "Define a data collection mechanism for each untracked benchmark before implementation." IF any Blind_Spot Audit_Log entries exist for the Active_Project.
8. WHEN no Audit_Log entries exist for the Active_Project, THE Recommendations section SHALL display: "Logic model appears structurally sound. Proceed to stakeholder validation."
9. THE Executive_Briefing SHALL apply clean typography, slate-coloured headings, and CSS page-break rules between major sections for print readiness.

---

### Requirement 10: Methodology Reference View

**User Story:** As a Policy_Analyst, I want an in-app methodology reference, so that I can understand the theoretical basis of the tool and cite it in my evaluation documentation.

#### Acceptance Criteria

1. WHEN the "Methodology" nav item is clicked, THE Keystone SHALL display the `#view-methodology` panel with the title "Programme Theory & Logic Model Reference".
2. THE `#view-methodology` SHALL contain a "Theory of Change" section with 2–3 paragraphs explaining the Input → Activity → Output → Outcome causal chain in plain professional language referencing policy evaluation best practice.
3. THE `#view-methodology` SHALL contain a "Common Logic Failures" section with a table containing three rows: Dead End, Miracle Leap, and Blind Spot, each with columns for Error Type, Description, and How to Fix.
4. THE `#view-methodology` SHALL contain a "DRIPA Alignment Notes" section with 2–3 paragraphs explaining how the tool relates to BC DRIPA Section 7 joint decision-making, referencing Indigenous data sovereignty and OCAP principles as evaluation considerations.

---

### Requirement 11: Demo Project Pre-Loading

**User Story:** As a Policy_Analyst opening Keystone for the first time, I want to see a realistic pre-loaded example, so that I can immediately understand how the tool works without having to create data from scratch.

#### Acceptance Criteria

1. WHEN the application loads AND `ks_projects` is empty, THE Keystone SHALL seed a demo Project with `id: "demo-001"`, `name: "DRIPA Section 7 Joint Decision-Making Agreement"`, `department: "BC Ministry of Indigenous Relations and Reconciliation"`, `mandate: "DRIPA Alignment"`, and `createdAt: "2025-09-15T09:00:00Z"`.
2. WHEN the demo Project is seeded, THE Keystone SHALL also seed exactly 8 Framework_Components associated with `projectId: "demo-001"` covering 2 Inputs, 2 Activities, 2 Outputs, and 2 Outcomes as specified.
3. WHEN the demo Project is seeded, THE Keystone SHALL set `demo-001` as the Active_Project and invoke `runAuditEngine("demo-001")`.
4. AFTER seeding and running the Audit_Engine on the demo project, THE Audit_Engine SHALL produce exactly 2 Medium-risk Blind_Spot entries and 0 High-risk entries, resulting in a Health_Score of 84.

---

### Requirement 12: Component Type Badges and Mandate Badges

**User Story:** As a Policy_Analyst, I want colour-coded badges on components and mandates, so that I can scan the logic model and project list at a glance without reading every label.

#### Acceptance Criteria

1. THE Framework_Component type badge colour SHALL be: slate-blue for "Input", `--cyan` for "Activity", `--green` for "Output", purple (`#7c3aed`) for "Outcome".
2. THE Project mandate badge colour SHALL be: `--amber` for "DRIPA Alignment", purple (`#7c3aed`) for "Self-Government Transition", `--slate` for "Service Delivery", `--green` for "Economic Development".
3. THE type badge and mandate badge SHALL be rendered as pill-shaped elements with rounded corners and appropriate contrast text colour.
