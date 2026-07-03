"""
DayOutputEngine — pure math, zero LLM calls (Proposed Enhancements, Entry 2).

Implements the evening-triggered, pre-ticked checklist described in the
build brief: every active (not yet completed/deferred/accepted-as-lost)
milestone in the committed Blueprint defaults to "done"; the user unticks
whatever was actually missed. This is the real data source that feeds
ReviewEngine.record_week_performance() at week rollover — previously that
method existed but had no genuine trigger anywhere in the system.

Milestones are addressed by their POSITION (index) in blueprint.milestones
for this submission — deliberately avoids adding an `id` field to
Milestone, since Milestone is also BlueprintAgent's output_schema target
and any field the LLM has to additionally populate is a new way for
generation to drift. Index-based addressing needs zero schema risk.
"""

from config import LIFE_HAPPENED_MISS_RATIO_THRESHOLD


class DayOutputEngine:
    def build_snapshot(self, blueprint) -> list[dict]:
        """
        Returns today's checklist: every milestone still active (not
        already completed, not deferred to next week, not accepted-as-
        lost), pre-ticked as done by default.
        """
        return [
            {
                "index": i,
                "title": m.title,
                "goal_title": m.goal_title,
                "task_title": m.task_title,
                "expected_hours": m.expected_hours,
                "ticked": True,
            }
            for i, m in enumerate(blueprint.milestones)
            if not m.completed and not m.deferred and not m.accepted_as_lost
        ]

    def apply_submission(self, blueprint, unticked_indices: set[int]) -> dict:
        """
        Applies the user's submission: any active milestone NOT in
        unticked_indices gets marked completed=True (mutates blueprint
        milestones in place — caller is responsible for re-writing
        blueprint to Shared State under the BlueprintAgent ownership tag,
        since Day Output is a deterministic sub-process of Blueprint
        completion tracking, not a competing writer).

        Returns a summary used both for immediate UI feedback and to
        accumulate this week's running totals for PRF calculation.
        """
        total_active = 0
        missed_count = 0
        missed_hours = 0.0

        for i, m in enumerate(blueprint.milestones):
            if m.completed or m.deferred or m.accepted_as_lost:
                continue
            total_active += 1
            if i in unticked_indices:
                missed_count += 1
                missed_hours += m.expected_hours
            else:
                m.completed = True

        miss_ratio = round(missed_count / total_active, 2) if total_active > 0 else 0.0

        return {
            "total_checked": total_active,
            "missed_count": missed_count,
            "missed_hours": round(missed_hours, 2),
            "miss_ratio": miss_ratio,
            "should_offer_life_happened": miss_ratio > LIFE_HAPPENED_MISS_RATIO_THRESHOLD,
        }
