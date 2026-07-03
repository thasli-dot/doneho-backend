# DoneHo Backend

Adaptive weekly execution planning system — deterministic math + real
Google ADK agents, kept strictly separate. Built against
`DoneHo_Antigravity_Build_Brief.md` (frozen spec).

## Setup

```bash
cd doneho_backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then paste your real GOOGLE_API_KEY into .env
```

## Run the end-to-end demo

```bash
python3 main.py
```

This exercises the full flow from Section 13 of the build brief, plus
Roadmap Entries 1, 2, 3, 5, 7, 8, 9: goal entry → clarification → sample
Blueprint → Pass 2 refinement → commit → Nudge Agent suggestions → a
reported disruption → an approved recovery (with proof the Blueprint
actually mutates) → a fresh Aether tip → an evening Day Output check-in
→ "Life Happened" → a second, similar disruption showing per-user
pattern learning in action.

## Project structure

```
doneho_backend/
├── config.py                   # frozen formula constants, model name, env
├── main.py                     # runnable end-to-end demo (now covers Entries 1,2,3,5,7,8,9)
├── orchestrator.py             # DoneHoOrchestrator — wires Event Bus + Shared State + engines + agents
│
├── models/
│   └── schemas.py               # every Pydantic model (Profile, Goal, Task, Blueprint,
│                                 # Milestone, DisruptionLog, DailyCheckIn, ADK output_schema
│                                 # targets, etc.)
│
├── data/
│   └── profession_defaults.py   # 21 profession presets for Weekly Capacity
│
├── engines/                     # DETERMINISTIC ENGINE — pure math, zero LLM calls
│   ├── capacity_engine.py       # Weekly Capacity + safety clamp
│   ├── review_engine.py         # PRF (Planning Reliability Factor), earned from history
│   ├── commitment_engine.py     # Recommended Commitment + Commitment Contract range
│   ├── reserve_engine.py        # Reserve Hours (never shown to user)
│   ├── lifeload_engine.py       # LifeLoad, Planning Confidence, Focus classification
│   ├── absorption_engine.py     # Entry 1 — Stage 1 (silent) + Stage 2 (LifeLoad renegotiation)
│   ├── day_output_engine.py     # Entry 2 — evening checklist snapshot + submission handling
│   ├── recovery_applier.py      # Entry 3 fix — applies an approved Stage 3 step to the Blueprint
│   └── deterministic_engine.py  # orchestrates capacity/review/commitment/reserve/lifeload,
│                                 # sole writer to Shared State's deterministic fields
│
├── core/
│   ├── shared_state.py          # SharedExecutionState — enforces one-writer-per-field
│   ├── event_bus.py             # pub/sub Event Bus + canonical event names
│   └── agent_runner.py          # shared ADK Runner/session boilerplate for all agents
│
└── agents/                      # AI AGENTS — real google-adk Agents with Gemini reasoning
    ├── clarification_agent.py   # flags genuinely ambiguous tasks only
    ├── blueprint_agent.py       # decomposes goals/tasks into concrete milestones
    ├── nudge_agent.py           # Opportunity Map / Day Boosters / Smart Spend + Entry 9 gain handling
    ├── search_subagent.py       # AgentTool wrapper around google_search (used by Nudge, Entry 4)
    ├── location_subagent.py     # AgentTool wrapper around google_maps_grounding (Entry 5)
    ├── aether_presence_agent.py # Entry 5 — proactive, state-aware Aether commentary
    └── recalibration_agent.py   # Stage 0 cost estimate (now history-aware, Entry 7) +
                                  # Stage 3 strict recovery hierarchy
```

## Architecture invariants (do not violate these while extending)

- **One Owner Per Data Object / One Writer Rule** — `SharedExecutionState`
  enforces this at runtime via `write(owner, field, value)`. Writing a
  field from the wrong component raises `OwnershipViolation` immediately
  instead of silently corrupting state.
- **Deterministic math and AI reasoning never mix.** Everything in
  `engines/` is pure Python, zero LLM calls. Everything in `agents/` is a
  real ADK `Agent` — no hand-rolled heuristics standing in for reasoning.
- **Agents never call each other directly.** All sequencing goes through
  `EventBus` in `orchestrator.py`.
- **"Reserve Hours" (the term and the number) is never surfaced to the
  user.** Enforced via `RecalibrationAgent`'s instruction — see the
  docstring at the top of `agents/recalibration_agent.py`.

## Entry 1 — Staged Silent Absorption (built)

`report_disruption(description, direction=LOSS)` runs a 4-stage flow
instead of always doing a single LLM decision + mandatory approval:

| Stage | What happens | LLM call? | Approval needed? |
|---|---|---|---|
| 0 — Cost estimation | Reasons over the disruption text to estimate hours lost, using this user's past disruption history as context (Entry 7) | Yes | — |
| 1 — Silent absorption | If it fits inside remaining Reserve, absorb quietly | **No** — pure math (`engines/absorption_engine.py`) | **No** |
| 2 — LifeLoad renegotiation | If Reserve alone isn't enough, compute a small capped LifeLoad increase to cover the shortfall | **No** — pure math, derived directly from the frozen LifeLoad formula | Yes |
| 3a — Hierarchy (flexible task) | Falls back to the strict ordered Recovery Hierarchy | Yes | Yes |
| 3b — Accepted as lost (rigid task) | Task can't be rescheduled — marked lost | **No** | Yes |

Whichever stage resolves it, the result always comes back as the same
`RecalibrationProposal` shape (`state.last_disruption_outcome`), so your
frontend doesn't need to branch on which stage fired — just check
`requires_approval`. If `True`, call `approve_recalibration()` once the
user confirms; if `False` (Stage 1), it's already applied.

**Where the numbers live:** `state.reserve_used_this_week` and
`state.lifeload_renegotiated_increase` are running counters for the
current week, owned by `RecalibrationAgent`. The base `lifeload` value
computed by `DeterministicEngine` is never overwritten directly — read
`state.effective_lifeload` (base + renegotiated increase) anywhere you'd
display LifeLoad. Call `orchestrator.start_new_week()` at week rollover
to reset both counters (and to record the week's real performance — see
Entry 2 below).

## Entry 2 — Daily Check-In / Day Output (built)

`orchestrator.get_day_output_checklist()` returns today's active
milestones, pre-ticked as done by default (each item carries its
position `index`, used to address it). `orchestrator.submit_day_output(day_label, unticked_indices)`
marks everything else `completed=True` on the Blueprint, accumulates
this week's running totals in `state.day_output_totals`, appends a full
`DailyCheckIn` record to `state.daily_checkins`, and returns
`should_offer_life_happened=True` if more than half of today's items
were missed (Entry 8 hook).

**This is what makes the PRF-earning loop real:** `orchestrator.start_new_week()`
now reads `state.day_output_totals` and calls
`ReviewEngine.record_week_performance()` with real, user-submitted data
— previously that method existed but nothing ever called it outside a
manually-constructed test.

## Entry 3 — Hierarchy Approval Now Mutates the Blueprint (fix, built)

Previously, approving a Stage 3 `HIERARCHY_RECOVERY` or `ACCEPTED_AS_LOST`
proposal updated `ExecutionContract.approved = True` but never touched
the actual Blueprint — the recovery step was decided but never applied.
`engines/recovery_applier.py` closes this gap: `approve_recalibration()`
now calls `RecoveryApplier.apply()`, which deterministically mutates the
Blueprint according to which step was chosen (stretch total hours, trim
scope proportionally, defer a milestone, or drop a goal's remaining
active milestones — always in reverse-Traffic order per Stage 3's own
decision, never re-decided here). This keeps the "judgment is AI,
execution of that judgment is pure code" split intact — Stage 3 decides,
`RecoveryApplier` deterministically applies.

## Entry 5 — Proactive Aether Presence (built)

`orchestrator.request_aether_tip()` returns a fresh, state-aware
one-liner from Aether — never a canned string. It's grounded in real
current values (LifeLoad, whether a leisure/mindfulness goal exists,
how many disruptions have happened this week, upcoming milestones).
If `Profile.location` is set, it may also weave in one real nearby idea
via `agents/location_subagent.py` (`google_maps_grounding`, same
`AgentTool` pattern as Entry 4's search tool, since grounding tools can't
share an agent with `output_schema`).

## Entry 7 — Per-User Pattern Learning (built)

Every LOSS disruption is already logged to `state.disruption_log`. Stage
0 cost estimation now receives a deterministically-built (no LLM)
summary of this user's most recent past disruptions
(`orchestrator._build_historical_context()`) as real prior context, so
Gemini can reason "this is similar to a past hospital visit that cost
~3.5h" instead of estimating from zero every single time. Demonstrated
in `main.py`'s Step 9 with a second, similar disruption after the first.

## Entry 8 — "Life Happened" (built)

`orchestrator.trigger_life_happened()` is a distinct, no-reason-needed
trigger, only valid after at least one Day Output submission today.
Unlike the text-based `/disruption` flow, its cost is computed directly
and deterministically from that day's actual missed milestones — no
Stage 0 LLM call needed, since the cost is already known exactly. It
then feeds into the exact same Stage 1-3 absorption flow
(`orchestrator._run_absorption_stages_1_to_3`, shared by both entry
points) as any other loss disruption.

## Entry 9 — Positive Disruption ("Gain") Handling (built)

`report_disruption(description, direction=GAIN)` routes to a dedicated
Nudge Agent extension (`agents/nudge_agent.py::run_gain_suggestions`)
that estimates the freed hours and suggests how to use them (pull a
milestone forward, an Opportunity Map item, a Smart Spend idea), using
the same 15-technique reasoning process as regular Nudge output. Results
land in `state.last_gain_suggestions`. No approval gate — these are
suggestions, not a Blueprint mutation, same as regular Nudge output.

## What's still NOT built here (by design)

- **Entry 4 / Entry 6 UI wiring** — the backend for real search links
  (Entry 4) and mid-week goal/task editing (Entry 6, already exposed via
  `/modify-task` and `/modify-goal`) is complete; what's not done is
  connecting Lovable's UI to actually call these existing endpoints.
- **Future Vision (Section 11 of the build brief)** — cross-cohort
  pattern learning and autonomous booking/purchasing are explicitly out
  of scope, by design, not oversights.

## A note on the Reserve Engine

`ReserveEngine` and the "Reserve Hours" number exist and are calculated
correctly — they're just never rendered to the user anywhere in the UI or
in any agent-generated message. If you're debugging and want to see the
real number, read `orchestrator.state.reserve_hours` directly; don't
thread it into any user-facing string.
