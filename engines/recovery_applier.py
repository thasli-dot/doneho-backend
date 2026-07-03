"""
RecoveryApplier — pure math, zero LLM calls (Proposed Enhancements, Entry 3
fix). Applies an APPROVED Stage 3 recovery step to the Blueprint.

Why this needs to exist: Stage 3's LLM call (recalibration_agent.py) only
DECIDES which recovery step to take -- it never touches the Blueprint
itself. Before this fix, approving a Stage 3 proposal updated
ExecutionContract but never actually mutated milestones/hours, so
"stretch commitment" or "drop a goal" were decided but never applied.
This module is the deterministic "apply" half, kept separate from the
LLM "decide" half per the architecture's core principle: judgment is AI,
execution of that judgment on numbers is pure code.

Uses the same Milestone flags DayOutputEngine reads (completed / deferred
/ accepted_as_lost) so both entries share one consistent "is this
milestone still active this week" definition -- never two competing
schemes for the same concept.
"""

from models.schemas import Blueprint, ExecutionContract, RecoveryStep, Goal


class RecoveryApplier:
    def apply(self, blueprint: Blueprint, contract: ExecutionContract, goals: list[Goal]) -> Blueprint:
        step = contract.recovery_step
        hours_lost = contract.estimated_hours_lost or 0.0

        if step == RecoveryStep.STRETCH_REMAINING_DAYS:
            return self._stretch(blueprint, hours_lost)
        if step == RecoveryStep.REDUCE_SPRINT_SCOPE:
            return self._reduce_scope(blueprint, hours_lost)
        if step == RecoveryStep.EXTEND_MILESTONE_NEXT_WEEK:
            return self._extend_milestone(blueprint, contract)
        if step == RecoveryStep.REDUCE_OR_DROP_GOAL:
            return self._drop_goal_milestones(blueprint, contract)

        # ACCEPTED_AS_LOST (rigid task) and anything unrecognized: no
        # structural Blueprint change. The miss is simply accepted --
        # nothing to reschedule, nothing to trim elsewhere. If a specific
        # task was identified, mark it accepted_as_lost so Day Output
        # correctly excludes it from future active checklists.
        if contract.affected_task_id:
            for m in blueprint.milestones:
                if m.task_id == contract.affected_task_id:
                    m.accepted_as_lost = True
        return blueprint

    def _active(self, blueprint: Blueprint) -> list:
        return [m for m in blueprint.milestones if not m.completed and not m.deferred and not m.accepted_as_lost]

    # ------------------------------------------------------------------
    def _stretch(self, blueprint: Blueprint, hours_lost: float) -> Blueprint:
        """Smallest possible adjustment: absorb the lost hours by
        slightly widening this week's total commitment, rather than
        touching any individual milestone."""
        blueprint.weekly_commitment_hours = round(blueprint.weekly_commitment_hours + hours_lost, 2)
        return blueprint

    def _reduce_scope(self, blueprint: Blueprint, hours_lost: float) -> Blueprint:
        """Trim the remaining sprint proportionally across all active
        milestones, so the total drops by hours_lost. Never pushes an
        individual milestone below 0."""
        active = self._active(blueprint)
        total_active_hours = sum(m.expected_hours for m in active)

        if total_active_hours <= 0:
            return blueprint

        remaining_to_trim = min(hours_lost, total_active_hours)
        for m in active:
            share = m.expected_hours / total_active_hours
            m.expected_hours = round(max(m.expected_hours - remaining_to_trim * share, 0.0), 2)

        blueprint.weekly_commitment_hours = round(
            max(blueprint.weekly_commitment_hours - remaining_to_trim, 0.0), 2
        )
        return blueprint

    def _extend_milestone(self, blueprint: Blueprint, contract: ExecutionContract) -> Blueprint:
        """Mark the affected milestone (or, if none was identified, the
        single largest active milestone) as deferred -- Day Output and
        future Blueprint totals both exclude it via the shared `deferred`
        flag."""
        target = None
        if contract.affected_task_id:
            target = next(
                (m for m in blueprint.milestones if m.task_id == contract.affected_task_id and not m.deferred and not m.completed and not m.accepted_as_lost),
                None,
            )
        if target is None:
            active = self._active(blueprint)
            if not active:
                return blueprint
            target = max(active, key=lambda m: m.expected_hours)

        target.deferred = True
        blueprint.weekly_commitment_hours = round(
            max(blueprint.weekly_commitment_hours - target.expected_hours, 0.0), 2
        )
        return blueprint

    def _drop_goal_milestones(self, blueprint: Blueprint, contract: ExecutionContract) -> Blueprint:
        """Remove this week's remaining ACTIVE milestones for the
        affected goal (chosen by Stage 3 in reverse-Traffic order already
        -- this method just applies whichever goal_id it was given). The
        goal itself is NOT deleted from the user's goal list -- that's a
        separate, explicit Modify action, not an automatic side effect of
        a single disruption. Already-completed milestones for that goal
        are left untouched (they're done, nothing to reduce)."""
        if not contract.affected_goal_id:
            return blueprint

        kept = []
        dropped_hours = 0.0
        for m in blueprint.milestones:
            is_active = not m.completed and not m.deferred and not m.accepted_as_lost
            if m.goal_id == contract.affected_goal_id and is_active:
                dropped_hours += m.expected_hours
            else:
                kept.append(m)

        blueprint.milestones = kept
        blueprint.weekly_commitment_hours = round(
            max(blueprint.weekly_commitment_hours - dropped_hours, 0.0), 2
        )
        return blueprint
