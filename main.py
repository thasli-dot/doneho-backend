"""
DoneHo — end-to-end demo runner (Build Brief, Section 13: "What Done
Should Look Like"). Run this directly to exercise the full flow:

  1. Enter 2-3 goals with tasks
  2. Ambiguous tasks get clarified
  3. A sample Blueprint appears
  4. Pass 2 onboarding visibly changes the numbers and the Blueprint
  5. Nudge Agent produces short, specific, checkable suggestions
  6. Reporting a disruption produces a calm, hierarchy-respecting
     recovery proposal — never mentions Reserve Hours, no guilt language
  7. A fresh, state-aware Aether tip (Entry 5)
  8. Day Output — evening checklist, submit with a miss (Entry 2),
     proving the Blueprint actually mutates on Stage 3 approval (Entry 3)
  9. "Life Happened" — no-reason-needed trigger after a rough day (Entry 8)
 10. A second disruption showing per-user pattern learning in action
     (Entry 7) — Stage 0 now has real history to reason over

Requires GOOGLE_API_KEY set in .env (see .env.example).
"""

from models.schemas import Profile, Goal, Task, GoalCategory
from orchestrator import DoneHoOrchestrator, new_goal_id, new_task_id


def build_sample_goals() -> list[Goal]:
    return [
        Goal(
            id=new_goal_id(),
            category=GoalCategory.STUDY_AND_LEARNING,
            traffic=0.7,
            volatility=0.4,
            tasks=[Task(id=new_task_id(), title="Learn Python")],
        ),
        Goal(
            id=new_goal_id(),
            category=GoalCategory.HEALTH_AND_WELLNESS,
            traffic=0.5,
            volatility=0.3,
            tasks=[Task(id=new_task_id(), title="Workout")],
        ),
        Goal(
            id=new_goal_id(),
            category=GoalCategory.LEISURE_AND_RECREATION,
            traffic=0.2,
            volatility=0.2,
            tasks=[Task(id=new_task_id(), title="Read a novel")],
        ),
    ]


def print_disruption_outcome(orchestrator, label: str):
    """
    Stage 1 (silent absorption) never creates an execution_contract --
    that's correct behavior, not a bug. Always read last_disruption_outcome
    first; only look at execution_contract if approval is actually needed.
    """
    outcome = orchestrator.state.last_disruption_outcome
    print(f"{label}: {outcome.outcome.value}")
    print(f"Message to user: {outcome.message}")
    if outcome.requires_approval:
        print("(Awaiting user approval before this is applied.)")
    else:
        print("(Auto-resolved silently -- no approval needed.)")
    return outcome


def main():
    profile = Profile(name="Chinju", profession="Product Manager (job seeking)", location="Bengaluru")
    orchestrator = DoneHoOrchestrator(profile)

    print("=== Step 1: submit goals/tasks ===")
    goals = build_sample_goals()
    orchestrator.submit_goals(goals)

    ambiguous = [t for g in orchestrator.state.goals for t in g.tasks if not t.clarified]
    if ambiguous:
        print(f"Clarification needed for {len(ambiguous)} task(s):")
        for t in ambiguous:
            print(f"  - {t.title}: {t.clarification_note}")
        answers = {t.id: "From scratch, basics first" for t in ambiguous}
        orchestrator.answer_clarifications(answers)
    else:
        print("No ambiguous tasks — skipping straight to Blueprint.")

    print("\n=== Step 2: sample Blueprint (Pass 1) ===")
    bp = orchestrator.state.blueprint
    print(f"LifeLoad: {orchestrator.state.lifeload} | Confidence: {orchestrator.state.planning_confidence}")
    print(f"Weekly commitment: {bp.weekly_commitment_hours}h")
    for m in bp.milestones:
        print(f"  [{m.goal_title} > {m.task_title}] {m.title} ({m.expected_hours}h)")

    print("=== Step 3: Pass 2 — real-life context ===")
    orchestrator.submit_pass2(caregiving_hours=6, planned_event_hours=3)
    bp = orchestrator.state.blueprint
    print(f"LifeLoad (updated): {orchestrator.state.lifeload} | Confidence: {orchestrator.state.planning_confidence}")
    print(f"Weekly commitment (updated): {bp.weekly_commitment_hours}h")

    print("=== Step 4: commit + Nudge Agent ===")
    orchestrator.commit_blueprint()
    suggestions = orchestrator.state.suggestions
    for item in suggestions["opportunity_map"][:3]:
        print(f"  [Opportunity Map] {item.title} — {item.description}")
    for item in suggestions["day_boosters"][:3]:
        print(f"  [Day Booster] {item.title} — {item.description}")
    for item in suggestions["smart_spend"][:3]:
        link_note = f" | Link: {item.link}" if item.link else ""
        print(f"  [Smart Spend] {item.title} — {item.description}{link_note}")

    print("=== Step 5: report a disruption ===")
    hours_before = orchestrator.state.blueprint.weekly_commitment_hours
    orchestrator.report_disruption("Emergency hospital visit for my kid today")
    outcome = print_disruption_outcome(orchestrator, "Outcome")

    if outcome.requires_approval:
        orchestrator.approve_recalibration()
        hours_after = orchestrator.state.blueprint.weekly_commitment_hours
        print("Recalibration approved — Nudge Agent auto-cascaded and refreshed suggestions.")
        print(f"[Entry 3 check] Blueprint weekly_commitment_hours: {hours_before}h -> {hours_after}h "
              f"({'mutated' if hours_before != hours_after else 'unchanged'})")
    else:
        print("[Entry 1 check] Resolved silently via Stage 1 -- no Blueprint mutation needed, this is correct.")

    print("=== Step 6: a fresh Aether tip (Entry 5) ===")
    tip = orchestrator.request_aether_tip()
    print(f"Aether: {tip.tip}" + (" (used a real location idea)" if tip.used_location else ""))

    print("=== Step 7: Day Output — evening check-in (Entry 2) ===")
    checklist = orchestrator.get_day_output_checklist()
    print(f"Today's checklist ({len(checklist)} active items):")
    for item in checklist:
        print(f"  [{item['index']}] {item['title']} ({item['goal_title']})")
    unticked = {checklist[0]["index"]} if checklist else set()
    day_result = orchestrator.submit_day_output("Monday", unticked)
    print(f"Missed: {day_result['missed_titles']} ({day_result['missed_hours']}h)")
    print(f"Should offer Life Happened: {day_result['should_offer_life_happened']}")

    print("=== Step 8: 'Life Happened' (Entry 8) ===")
    orchestrator.trigger_life_happened()
    print_disruption_outcome(orchestrator, "Outcome")

    print("=== Step 9: a second disruption — pattern learning in action (Entry 7) ===")
    print(f"(This user now has {len(orchestrator.state.disruption_log)} logged disruptions "
          f"Stage 0 can reason over as history)")
    orchestrator.report_disruption("Another hospital visit, similar to before")
    outcome2 = print_disruption_outcome(orchestrator, "Outcome")
    print(f"(Estimated hours lost this time: {outcome2.estimated_hours_lost}h — Stage 0 had real history to reason over)")


if __name__ == "__main__":
    main()
