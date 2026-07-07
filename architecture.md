# DoneHo — Architecture

---

## 1. Product Overview

DoneHo is not a generic to-do list or scheduler. Two ideas anchor it:

1. **Functional recovery over perfect recovery** — when disruption happens, the system finds the smallest adjustment that protects the user's goals, rather than ignoring the disruption or collapsing the whole plan.
2. **Deterministic math + AI reasoning, kept strictly separate** — anything calculable by formula is calculated by pure code, never guessed by an LLM. Anything requiring judgment is handled by a named, narrow AI agent.

Both principles held all the way through the build. Verified: no engine file imports an LLM client, no agent file contains a hardcoded formula.

## 2. Tech Stack — as shipped

- **Backend:** Python, FastAPI, `google-adk`. Deployed live on Render.
- **LLM:** Gemini, via `MODEL_NAME` in `config.py`.
- **Frontend:** Lovable-built React + TypeScript on TanStack Start, calling the real backend via server functions in `src/lib/doneho-api.functions.ts`.
- **Architecture pattern:** Event-driven, exactly as specified — `EventBus` + `SharedExecutionState`, agents never call each other directly.

## 3. Core Architecture — Six Agents

Six agents, each with one narrow, auditable job:

#
Agent
File
Scope

1
Clarification
`clarification_agent.py`
Flags genuinely ambiguous tasks only

2
Blueprint
`blueprint_agent.py`
Decomposes goals into concrete milestones

3
Nudge
`nudge_agent.py`
Two instructions: main suggestions + a Gain-handling variant for unexpectedly freed time (Entry 9)

4
Recalibration
`recalibration_agent.py`
Two instructions: Stage 0 cost estimation + Stage 3 hierarchy decision

5
Aether Presence
`aether_presence_agent.py`
Proactive, unprompted state-aware commentary

6
Aether Chat
`aether_chat_agent.py`
Reactive — answers the user's free-form questions, grounded in real session state

Two additional **AgentTools** (not independently orchestrated — invoked *by* the agents above, never called directly by the Orchestrator):

- `search_subagent.py` — real Google Search grounding, used by Nudge for Smart Spend links
- `location_subagent.py` — real Google Maps grounding, used by Aether Presence for nearby suggestions

**Every one of these ten `Agent()` instances uses a real `output_schema`** (Pydantic model), confirmed directly in code — none reasons in free text without a parseable contract.

### 3.1 Deterministic Engine — fully verified

- `CapacityEngine` — Weekly Capacity
- `ReviewEngine` — earned Planning Reliability Factor
- `CommitmentEngine` — Recommended Commitment
- `ReserveEngine` — Reserve Hours (never serialized to any API response — confirmed in `_serialize_blueprint()`)
- `DeterministicEngine` — orchestrates all of the above; sole writer to these Shared State fields

### 3.2 Shared Execution State — the rule held

One writer per field, enforced by `SharedExecutionState.write(owner, field, value)` at runtime. A wrong-owner write raises `OwnershipViolation` immediately — this was tested, not just asserted in a docstring.

## 4. The Real API Surface — 18 endpoints, not a demo stub

Every one of these is live on Render today:

Endpoint
Method
Maps to

`/session/start`
POST
New orchestrator instance

`/goals`
POST
Submit goals → Clarification Agent

`/clarify`
POST
Answer clarifications → Blueprint Agent

`/pass2`
POST
Refine constraints → Blueprint regenerates

`/commit`
POST
Lock Blueprint → Nudge Agent runs

`/nudge/regenerate`
POST
Fresh Opportunity Map / Boosters / Smart Spend

`/disruption`
POST
Report a disruption (LOSS or GAIN)

`/disruption/approve`
POST
Approve a proposed recovery step

`/modify-task`, `/modify-goal`
POST
Mid-week edits

`/day-output/checklist`
GET
Today's real milestone checklist

`/day-output`
POST
Evening submission

`/life-happened`
POST
No-reason-needed recovery trigger

`/aether-tip`
GET
Proactive Aether line

`/aether-chat`
POST
Reactive Aether chat

`/week/start`
POST
Week rollover

`/state`
GET
Full dashboard snapshot

`/health`
GET
Liveness check

## 5. Frontend Wiring — exactly what's real today, no rounding up

Precision here matters more than in any other section — this is the part most likely to be quietly overclaimed.

**Wired to the real backend, verified in code:**

- Onboarding → goals → clarification → Pass 2 → commit
- Disruption reporting + approval
- Day Output checklist + submission
- Life Happened trigger
- Day Boosters / Opportunity Map / Smart Spend (reading real `SuggestionItem` fields, including price/urgency/difficulty/task-pairing)
- The Dashboard's Aether chat panel

**Still on the original Lovable-gateway simulation, by deliberate scope decision:**

- The three onboarding-stage "Ask Aether" chats (goal selection, sliders, tasks) — no committed Blueprint exists yet at that point, so there's genuinely nothing real to ground a grounded answer in
- The small proactive "Aether insight" line shown at the top of several screens (`getAetherInsight`) — distinct from the Dashboard's main chat
- The Life Load Trend / Current Focus / Weekly Snapshot cards — explicitly tagged `MOCK` in the UI, since they need multi-week history that doesn't exist yet on a fresh account

### 5.1 Bugs Found and Fixed During Real End-to-End Testing

- **Disruption direction casing.** Backend's `DisruptionDirection` enum only accepts lowercase `"loss"`/`"gain"`. The frontend was sending uppercase `"LOSS"`, causing every disruption report to fail with `422 Unprocessable Content`. Fixed in both the API client and the call site.
- **Session-unaware localStorage restore.** The "return to Dashboard automatically" convenience feature saved onboarding inputs (name, goals, sliders) to the browser but never saved the actual `session_id` or real Blueprint data. A returning visit would show old goal labels with a dead session underneath — any real action would fail. Fixed: the restore now saves the real session state, and verifies with the backend (`GET /state`) that the session is still alive before trusting it; if the backend says it's gone, it clears the stale copy and returns to onboarding instead of showing a broken Dashboard.
- **CORS.** `DONEHO_ALLOWED_ORIGINS` was set to `*` during development. Locked down to the exact published frontend origin once a stable URL existed.

### 5.2 Known, current, non-blocking limitation

The Pass 2 hours-collection flow (caregiving/planned-event/other-constraint hours) reads a free-text reply and extracts the **first number found**, with no unit-awareness. Answering "2 hours a day" is silently misread as 2 hours for the entire week. No dedicated extraction agent exists for this field — unlike the disruption-reporting flow, which does use real LLM reasoning over free text. Mitigated by instructing users to answer in exact "X hours per week" phrasing; not yet fixed in code.

## 6. Data Model — unchanged, verified against `models/schemas.py`

26 Pydantic schema classes, including `AetherChatOutput`, and `SuggestionItem`'s enriched fields (`link`, `price`, `urgency`, `difficulty`, `task1`/`goal1`/`task2`/`goal2`, `action_type`) — added specifically so the Nudge Agent's real search-grounded output could reach the UI instead of being silently dropped.

## 7. Guardrails — verified present in `nudge_agent.py` and `recalibration_agent.py` instructions

These guardrails are present verbatim in the live agent instructions: no medical/financial/legal specifics, no reduced child supervision, no guilt-based language, every quantified claim requires a one-line justification, links only from real search results.

## 8. What's Explicitly Still Out of Scope

Both remain real long-term direction, deliberately not attempted yet:

- **Cross-user, cross-cohort pattern learning** — would need a real shared database, privacy-conscious aggregation, and opt-in consent; a multi-month effort, not a feature add
- **Autonomous booking/purchasing** — DoneHo suggests and links; the user completes the action
