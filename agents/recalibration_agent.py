"""
RecalibrationAgent (Build Brief Section 3.4/6 + Proposed Enhancements
Entry 1 — staged silent absorption, now built).

This file now contains TWO separate agents, because the staged flow
means only two of its four possible outcomes ever need an LLM call:

  Stage 0 — Disruption Cost Estimation (ALWAYS runs for a LOSS disruption)
      `run_cost_estimation()` — reasons over the free-text description to
      estimate hours lost, and tries to identify which goal/task it
      relates to (needed later to check is_flexible for Stage 3).

  Stage 1 — Silent absorption            -> engines/absorption_engine.py (NO LLM)
  Stage 2 — LifeLoad renegotiation        -> engines/absorption_engine.py (NO LLM)

  Stage 3 — Hierarchy fallback (ONLY runs if Stages 1 and 2 both fail to
      fully cover the disruption, AND the affected task is_flexible)
      `run_hierarchy_decision()` — picks exactly one step from the strict
      ordered Recovery Hierarchy, using the cost ALREADY estimated in
      Stage 0 rather than re-estimating.

  Stage 3, rigid task -> "accepted as lost" is fully deterministic (no
  LLM call at all) and is handled directly in orchestrator.py, since
  there's no judgment call left to make once flexibility is known.

Language rules (non-negotiable, enforced via instruction on both agents):
  - Never say "Reserve", "reserve hours", "buffer capacity", or any
    specific hours figure tied to hidden capacity.
  - Never guilt-based language ("you fell behind", "you missed your
    target"). Always calm, solution-focused.
"""

from google.adk.agents import Agent
from models.schemas import Goal, DisruptionCostEstimate, RecalibrationHierarchyOutput
from core.agent_runner import run_agent_sync
from config import MODEL_NAME

# ---------------------------------------------------------------------------
# Stage 0 — Cost Estimation
# ---------------------------------------------------------------------------

COST_ESTIMATION_INSTRUCTION = """You are DoneHo's disruption cost estimator.
You only activate for a disruption that COST the user time (a loss).

Step 1 — Reason over the user's free-text disruption description to
estimate how many hours it actually cost, including realistic secondary
effects (e.g. "emergency hospital visit for my kid" -> a reasoned estimate
covering the visit plus travel/waiting, not a guess pulled from nowhere
and not a fixed constant). If historical context about this user's past
similar disruptions is provided, use it as a real prior to sanity-check
or refine your estimate — don't ignore it, but don't blindly copy it
either if the current description clearly differs in scale.

Step 2 — Try to identify which single goal/task (from the list you're
given) this disruption most plausibly relates to, if any. If it's a
general schedule squeeze not tied to one specific task (e.g. "today just
got chaotic"), leave both id fields null — do not force a match.

Step 3 — Write a short internal reasoning_note explaining your hour
estimate in one sentence. This is for internal logging only, not shown
directly to the user, but must still avoid guilt language and must never
mention "reserve" or "buffer".

Return ONLY the structured output. No extra commentary."""


def build_cost_estimation_agent() -> Agent:
    return Agent(
        name="disruption_cost_estimator",
        model=MODEL_NAME,
        description="Estimates hours lost to a disruption and identifies the likely affected goal/task.",
        instruction=COST_ESTIMATION_INSTRUCTION,
        output_schema=DisruptionCostEstimate,
    )


def run_cost_estimation(
    disruption_description: str,
    goals: list[Goal],
    historical_context: str | None = None,
) -> DisruptionCostEstimate:
    """
    historical_context (Entry 7 — per-user pattern learning): an optional
    one-line summary of this user's past similar disruptions, built
    deterministically by the orchestrator from disruption_log (simple
    keyword-overlap matching, no LLM call) and passed in here so Stage 0
    remains exactly ONE LLM call, just with a richer prompt when history
    exists.
    """
    lines = []
    for g in goals:
        lines.append(f"- Goal id={g.id} ({g.category.value})")
        for t in g.tasks:
            lines.append(f"    - Task id={t.id}: \"{t.title}\" (flexible={t.is_flexible})")

    prompt = (
        f"Disruption reported by user: \"{disruption_description}\"\n\n"
        f"Active goals/tasks this week:\n" + "\n".join(lines)
    )
    if historical_context:
        prompt += f"\n\n{historical_context}"

    agent = build_cost_estimation_agent()
    return run_agent_sync(agent, prompt, DisruptionCostEstimate)


# ---------------------------------------------------------------------------
# Stage 3 — Hierarchy Fallback (flexible tasks only)
# ---------------------------------------------------------------------------

HIERARCHY_INSTRUCTION = """You are DoneHo's Recovery Hierarchy decision-maker.
You only activate when quieter recovery options have already been ruled
out for this disruption (silent absorption and a capped LifeLoad increase
both weren't enough) — your job is to pick exactly ONE next step.

You will be given the disruption description, the hours already
established as lost (do not re-estimate this — use the number given), and
the active goals with their Traffic values.

Choose exactly ONE recovery step, trying this EXACT order and stopping at
the first one that resolves the disruption:
  1. stretch_remaining_days — stretch commitment slightly for remaining days
  2. reduce_sprint_scope — reduce current sprint scope
  3. extend_milestone_next_week — extend the current milestone into next week
  4. reduce_or_drop_goal — LAST RESORT ONLY. Only consider goals in reverse
     Traffic order (lowest-Traffic goal first). If two or more goals are
     tied on Traffic and both are candidates, do NOT pick arbitrarily —
     set needs_tiebreak_input=true, leave affected_goal_id null, and your
     proposal_message should directly ask the user which goal to protect.

Write proposal_message: calm, short, solution-focused. NEVER use the word
"reserve", "buffer", or state any specific hidden-capacity hours figure.
NEVER use guilt language ("you fell behind", "you missed your target").
Describe the OUTCOME plainly, e.g. "Here's how we adjust to keep you on
track this week."

Return ONLY the structured output. No extra commentary."""


def build_hierarchy_agent() -> Agent:
    return Agent(
        name="recovery_hierarchy_agent",
        model=MODEL_NAME,
        description="Picks exactly one step from the strict ordered Recovery Hierarchy.",
        instruction=HIERARCHY_INSTRUCTION,
        output_schema=RecalibrationHierarchyOutput,
    )


def run_hierarchy_decision(
    disruption_description: str,
    estimated_hours_lost: float,
    goals: list[Goal],
) -> RecalibrationHierarchyOutput:
    goal_lines = [
        f"- id={g.id}, category={g.category.value}, traffic={g.traffic}"
        for g in goals
    ]
    prompt = (
        f"Disruption: \"{disruption_description}\"\n"
        f"Hours already estimated as lost: {estimated_hours_lost}\n\n"
        f"Active goals (for step 4, if needed):\n" + "\n".join(goal_lines)
    )
    agent = build_hierarchy_agent()
    return run_agent_sync(agent, prompt, RecalibrationHierarchyOutput)
