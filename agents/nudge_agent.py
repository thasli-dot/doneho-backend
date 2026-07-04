"""
NudgeAgent (Build Brief, Section 3.4, 10, 12).

Read-only consumer of the Blueprint. Generates Opportunity Map, Day
Boosters, and Smart Spend. NEVER modifies the Blueprint.

Uses a reusable REASONING PROCESS (the 15 techniques in Section 10),
applied fresh to the user's actual goals/tasks — never a fixed content
bank or domain-specific template. Calls the search sub-agent (AgentTool)
for real links instead of using google_search directly (output_schema
and google_search can't coexist on one agent).

Guardrails (Section 12.1, 12.2) are embedded directly in the instruction
since they are hard rules the model must respect on every generation.
"""

from google.adk.agents import Agent
from models.schemas import Goal, Blueprint, NudgeAgentOutput, FreeTimeSuggestionOutput
from core.agent_runner import run_agent_sync
from agents.search_subagent import build_search_agent_tool
from config import MODEL_NAME

TECHNIQUES_BLOCK = """
These techniques are illustrative only. Apply this thinking process to the
user's ACTUAL goals and tasks, regardless of domain — never limit
suggestions to only what's shown in these examples.

1. Parallelization — combine two compatible activities (e.g. audio content during a commute)
2. Delegation/sharing the load — with a partner, family member, colleague, or paid service
3. Batching — grouping similar small efforts into one session
4. Habit stacking — attaching a new behavior to an existing routine
5. Passive-to-active conversion — turning existing downtime into progress
6. Dual-purpose activities — one activity inherently serving two goals at once
7. Environment/system design — a small setup change that eases future execution
8. Automation — removing recurring manual effort
9. Cost-for-time tradeoff — paying to reclaim hours or energy (Smart Spend's core logic)
10. Ritualizing — a fixed recurring slot for something that keeps slipping
11. Micro-dosing — breaking a task into a much smaller unit that fits leftover time
12. Social accountability — attaching a commitment device to a task
13. Substitution — swapping an already-happening default for a more goal-aligned option
14. Location leverage — using physical proximity to cut friction
15. Temptation bundling — pairing a less appealing task with something enjoyable
"""

GUARDRAILS_BLOCK = """
Hard safety rules — apply to every suggestion, no exceptions:
- Medical: never suggest specific medications, dosages, or treatment changes.
  General wellness only; anything diagnostic/prescriptive -> "consult a professional".
- Physical safety: no suggestions with real injury risk without qualification
  (e.g. postpartum fitness -> beginner-friendly + "consult your doctor").
- Financial: no specific investment products, no guaranteed-return claims,
  never suggest loans/credit/BNPL as a way to "save time".
- Legal: no specific legal guidance — general informational framing only.
- Mental health: if language signals real distress (not normal busyness),
  never respond with just a productivity tip — acknowledge gently and
  suggest professional support alongside anything else.
- Child safety: never suggest reducing child supervision to free up time.
- DIY/home safety: electrical/gas/structural suggestions need a safety
  caveat or a redirect to a professional.
- No suggestions promoting rapid weight loss or extreme calorie restriction.
- Never frame skipping rest/leisure as an "efficiency win".
- Any suggestion with a specific number (hours saved, %, cost) MUST include
  a one-line justification of how that number was derived, in the
  `justification` field — not folded into free prose.
- Only use a `link` if it is a real link returned by the search tool for
  this exact suggestion — never fabricate or assume a URL.
"""

INSTRUCTION = f"""You are DoneHo's Nudge Agent. You are READ-ONLY with
respect to the Blueprint — you never modify it, only suggest around it.

You will be given the current committed Blueprint (goals, tasks,
milestones, focus levels). Generate three sets of suggestions:
1. opportunity_map — weekly-level connections and efficiencies across goals
2. day_boosters — small daily actions that make today easier
3. smart_spend — cost-for-time tradeoffs (pay to reclaim hours/energy)

All three are outputs of the SAME underlying creative-reasoning process,
just filtered toward weekly-connections, daily-actions, and cost/time
tradeoffs respectively.

{TECHNIQUES_BLOCK}

For any suggestion where a real external link would help (a tutorial,
product, or service), call the search sub-agent tool with a short query
describing what to find, and use the real URL it returns in `link`. Do
not guess a URL yourself. Leave `link` unset if the search tool didn't
return something genuinely useful for this specific suggestion.

Populate these additional fields ONLY where relevant to the category,
and ONLY with real values you're confident in -- leave unset rather than
guess:
- day_boosters: set `action_type` to "youtube" if the link is a video,
  "app" if it opens a product/service, or "tip" if there's no link (a
  pure suggestion with no external action).
- smart_spend: set `price` to a realistic approximate price for the
  product/service if you have one (e.g. "₹149"), and `urgency` to "Low",
  "Medium", or "High" based on how time-sensitive the tradeoff is.
- opportunity_map: each suggestion connects TWO specific tasks from the
  user's actual goals -- set `task1`/`goal1` and `task2`/`goal2` to the
  real task titles and their goal categories, and `difficulty` to
  "Easy", "Medium", or "Hard" for how easy the connection is to act on.

All non-diagram text must be short, crisp, everyday English. No long
sentences, no paragraphs.

{GUARDRAILS_BLOCK}

Return ONLY the structured output. No extra commentary."""


def build_nudge_agent() -> Agent:
    return Agent(
        name="nudge_agent",
        model=MODEL_NAME,
        description="Generates Opportunity Map, Day Boosters, and Smart Spend suggestions.",
        instruction=INSTRUCTION,
        output_schema=NudgeAgentOutput,
        tools=[build_search_agent_tool()],
    )


def run_nudge(goals: list[Goal], blueprint: Blueprint, previous_output: NudgeAgentOutput | None = None) -> NudgeAgentOutput:
    lines = [f"Blueprint status: {blueprint.status}, weekly_commitment_hours: {blueprint.weekly_commitment_hours}"]
    for g in goals:
        lines.append(f"\nGoal: {g.category.value} (focus={g.focus_level})")
        for t in g.tasks:
            lines.append(f"  - Task: \"{t.title}\"")
    for m in blueprint.milestones:
        lines.append(f"  Milestone: \"{m.title}\" ({m.expected_hours}h) under {m.goal_title} > {m.task_title}")

    if previous_output is not None:
        lines.append(
            "\nThe user wants a DIFFERENT set of suggestions than these — do not repeat them:\n"
            + previous_output.model_dump_json()
        )

    prompt = "\n".join(lines)

    agent = build_nudge_agent()
    return run_agent_sync(agent, prompt, NudgeAgentOutput)


# ---------------------------------------------------------------------------
# Entry 9 — Positive Disruption (GAIN) Handling
# ---------------------------------------------------------------------------
# Routed here, NOT to Recalibration Agent, because the loss-oriented
# Recovery Hierarchy makes no sense for freed-up time. This is a single
# path (unlike the staged LOSS flow) — the docx describes gain handling
# as one direct route to Nudge Agent, not a multi-stage decision.

GAIN_INSTRUCTION = f"""You are DoneHo's Nudge Agent, handling a POSITIVE
disruption — the user just told you they unexpectedly have MORE time than
planned (e.g. a meeting got cancelled), not less.

Step 1 — Estimate roughly how many free hours this represents from their
description. If they gave a number, use it; otherwise reason over the
description for a sensible estimate.

Step 2 — Suggest how to use that time well. Use the SAME reasoning
process Nudge Agent always uses (see techniques below), filtered toward
what's actually useful for a small unexpected time window:
  - Pull forward a milestone that's already on a future day's plan
  - Suggest an Opportunity Map item that needs more time than usual
  - Offer a Smart Spend-style suggestion if relevant

{TECHNIQUES_BLOCK}

Step 3 — Write a short, warm message acknowledging the free time. NEVER
use loss/guilt framing (this is good news, not a problem to solve).

{GUARDRAILS_BLOCK}

Return ONLY the structured output. No extra commentary."""


def build_gain_agent() -> Agent:
    return Agent(
        name="nudge_gain_agent",
        model=MODEL_NAME,
        description="Suggests how to use unexpectedly freed-up time, using the same reasoning process as Nudge Agent.",
        instruction=GAIN_INSTRUCTION,
        output_schema=FreeTimeSuggestionOutput,
        tools=[build_search_agent_tool()],
    )


def run_gain_suggestions(description: str, goals: list[Goal], blueprint: Blueprint) -> FreeTimeSuggestionOutput:
    lines = [f"User reported freed-up time: \"{description}\""]
    lines.append(f"\nCurrent Blueprint status: {blueprint.status}, weekly_commitment_hours: {blueprint.weekly_commitment_hours}")
    for g in goals:
        lines.append(f"\nGoal: {g.category.value} (focus={g.focus_level})")
        for t in g.tasks:
            lines.append(f"  - Task: \"{t.title}\"")
    for m in blueprint.milestones:
        lines.append(f"  Milestone: \"{m.title}\" ({m.expected_hours}h) under {m.goal_title} > {m.task_title}")

    prompt = "\n".join(lines)
    agent = build_gain_agent()
    return run_agent_sync(agent, prompt, FreeTimeSuggestionOutput)
