"""
DoneHo — Agent Evals

A lightweight, real evaluation harness — not a cosmetic checkbox. This
runs actual test cases against the actual live agents (blueprint_agent,
recalibration_agent, nudge_agent) and checks their outputs against
concrete, defined pass/fail criteria pulled directly from this project's
own stated guardrails — not invented for this file.

This does NOT require any running server or deployed API — it imports
the agent modules directly and calls them, same code path the real
backend uses. Requires GOOGLE_API_KEY to be set (same .env as the rest
of the project), since these are real Gemini calls, not mocked.

Run: python3 evals/run_evals.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import Goal, Task, GoalCategory, Blueprint, Milestone
from agents.blueprint_agent import run_blueprint
from agents.recalibration_agent import run_cost_estimation
from agents.nudge_agent import run_nudge


# ---------------------------------------------------------------------------
# Eval 1 — Blueprint Agent: "never generic phase labels" guardrail
# ---------------------------------------------------------------------------
# This is a real, explicit rule already written into the agent's own
# instruction (blueprint_agent.py): milestone titles must never be one of
# a small set of generic phase words. This eval checks that rule actually
# holds on real generated output, rather than just trusting the prompt.

GENERIC_PHRASES = {
    "foundation", "practice", "revision", "evaluation",
    "getting started", "deep dive", "phase 1", "phase 2", "phase 3",
}

BLUEPRINT_TEST_CASES = [
    {
        "goal_id": "g1",
        "category": GoalCategory.STUDY_AND_LEARNING,
        "tasks": [Task(id="t1", title="Learn SQL")],
        "hours": 5.0,
    },
    {
        "goal_id": "g2",
        "category": GoalCategory.HEALTH_AND_WELLNESS,
        "tasks": [Task(id="t2", title="C-section recovery")],
        "hours": 3.0,
    },
    {
        "goal_id": "g3",
        "category": GoalCategory.FAMILY_AND_CHILDCARE,
        "tasks": [Task(id="t3", title="Childcare for 1-year-old")],
        "hours": 4.0,
    },
]


def eval_blueprint_milestones():
    print("\n=== Eval 1: Blueprint Agent — no generic phase labels ===")
    passed, failed = 0, 0
    for case in BLUEPRINT_TEST_CASES:
        goal = Goal(
            id=case["goal_id"],
            category=case["category"],
            traffic=0.7,
            volatility=0.5,
            tasks=case["tasks"],
        )
        result = run_blueprint([goal], {case["goal_id"]: case["hours"]})

        if not result.milestones:
            print(f"  FAIL [{case['tasks'][0].title}]: no milestones generated at all")
            failed += 1
            continue

        case_ok = True
        for m in result.milestones:
            title_lower = m.title.strip().lower()
            if title_lower in GENERIC_PHRASES:
                print(f"  FAIL [{case['tasks'][0].title}]: generic milestone title '{m.title}'")
                case_ok = False
            if title_lower == case["tasks"][0].title.strip().lower():
                print(f"  FAIL [{case['tasks'][0].title}]: milestone just repeats the task title verbatim")
                case_ok = False

        if case_ok:
            titles = [m.title for m in result.milestones]
            print(f"  PASS [{case['tasks'][0].title}]: {len(titles)} concrete milestone(s) — e.g. \"{titles[0]}\"")
            passed += 1
        else:
            failed += 1

    return passed, failed


# ---------------------------------------------------------------------------
# Eval 2 — Recalibration Agent Stage 0: cost estimates are sane
# ---------------------------------------------------------------------------
# A real disruption cost estimate should be a positive number, and bounded
# to something plausible for a single reported event (a week only has 168
# hours total; no single disruption should ever eat more than a large
# fraction of that). This catches the model returning nonsense, zero, or
# a runaway number.

DISRUPTION_TEST_CASES = [
    "My mother was hospitalised, I lost 3 days of study time",
    "Kid has a fever, need a hospital visit today",
    "Traffic made me lose an hour this morning",
    "Unexpected hospital visit, lost 2 hours today",
]

MAX_PLAUSIBLE_HOURS = 60.0  # a single reported disruption should never claim more than this


def eval_disruption_cost_estimates():
    print("\n=== Eval 2: Recalibration Agent — cost estimates are sane ===")
    dummy_goal = Goal(
        id="g1",
        category=GoalCategory.STUDY_AND_LEARNING,
        traffic=0.7,
        volatility=0.5,
        tasks=[Task(id="t1", title="Crack UPSC 2027")],
    )
    passed, failed = 0, 0
    for description in DISRUPTION_TEST_CASES:
        result = run_cost_estimation(description, [dummy_goal])
        ok = True
        if result.estimated_hours_lost <= 0:
            print(f"  FAIL [\"{description}\"]: estimated_hours_lost is not positive ({result.estimated_hours_lost})")
            ok = False
        if result.estimated_hours_lost > MAX_PLAUSIBLE_HOURS:
            print(f"  FAIL [\"{description}\"]: estimated_hours_lost implausibly high ({result.estimated_hours_lost})")
            ok = False
        if not result.reasoning_note or not result.reasoning_note.strip():
            print(f"  FAIL [\"{description}\"]: no reasoning_note provided")
            ok = False

        if ok:
            print(f"  PASS [\"{description}\"]: {result.estimated_hours_lost}h — \"{result.reasoning_note[:60]}\"")
            passed += 1
        else:
            failed += 1

    return passed, failed


# ---------------------------------------------------------------------------
# Eval 3 — Nudge Agent: numeric claims require justification
# ---------------------------------------------------------------------------
# This is a real, explicit rule stated in the project's own architecture
# docs: "every quantified claim requires a one-line justification." This
# eval checks that invariant actually holds on real generated suggestions.


def eval_nudge_justification_invariant():
    print("\n=== Eval 3: Nudge Agent — numeric claims carry justification ===")
    goal = Goal(
        id="g1",
        category=GoalCategory.STUDY_AND_LEARNING,
        traffic=0.7,
        volatility=0.5,
        tasks=[Task(id="t1", title="Crack UPSC 2027")],
    )
    blueprint = Blueprint(
        weekly_commitment_hours=15.0,
        milestones=[
            Milestone(title="Review current affairs (Mon-Wed)", expected_hours=3.0, goal_id="g1",
                      goal_title="Study and Learning", task_id="t1", task_title="Crack UPSC 2027"),
        ],
        reserve_hours=4.0,
        lifeload=45.0,
        planning_confidence=0.8,
        status="committed",
    )
    result = run_nudge([goal], blueprint)

    all_suggestions = result.opportunity_map + result.day_boosters + result.smart_spend
    if not all_suggestions:
        print("  FAIL: no suggestions generated at all")
        return 0, 1

    passed, failed = 0, 0
    for s in all_suggestions:
        if s.time_saved_minutes is not None and not s.justification:
            print(f"  FAIL [\"{s.title}\"]: has time_saved_minutes={s.time_saved_minutes} but no justification")
            failed += 1
        else:
            passed += 1

    print(f"  {passed}/{passed + failed} suggestions correctly paired numbers with justification")
    return passed, failed


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY not set. Copy .env.example to .env and add your key first.")
        sys.exit(1)

    total_passed, total_failed = 0, 0
    for eval_fn in (eval_blueprint_milestones, eval_disruption_cost_estimates, eval_nudge_justification_invariant):
        p, f = eval_fn()
        total_passed += p
        total_failed += f

    print(f"\n=== TOTAL: {total_passed} passed, {total_failed} failed ===")
    sys.exit(1 if total_failed > 0 else 0)
