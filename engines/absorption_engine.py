"""
AbsorptionEngine — pure math, zero LLM calls (Proposed Enhancements, Entry 1).

Implements Stage 1 (silent absorption) and Stage 2 (LifeLoad
renegotiation) of the staged disruption-recovery flow. Both are pure
deterministic checks against Shared State numbers — Stage 1 explicitly
requires NO LLM call per the roadmap spec, and Stage 2 is a direct
arithmetic consequence of the frozen LifeLoad formula, not a fresh
"guess" that needs reasoning.

Stage 3 (hierarchy fallback / accepted-as-lost) is NOT here — that's
handled by RecalibrationAgent (flexible tasks, needs LLM judgment) or
directly by the orchestrator (rigid tasks, deterministic "accepted as
lost", no LLM needed either).
"""

from config import (
    LIFELOAD_WEIGHT_COMMITMENT_RATIO,
    STAGE2_MAX_LIFELOAD_INCREASE_POINTS_PER_WEEK,
    STAGE2_LIFELOAD_CEILING,
)


class AbsorptionEngine:
    def try_silent_absorption(self, estimated_hours_lost: float, remaining_reserve: float) -> dict | None:
        """
        Stage 1. If the disruption's estimated cost fits entirely inside
        whatever Reserve is left this week, absorb it quietly: no
        interruption, no approval, LifeLoad completely untouched.
        Returns None if Reserve alone isn't enough (falls through to Stage 2).
        """
        if estimated_hours_lost <= remaining_reserve:
            return {
                "absorbed_hours": round(estimated_hours_lost, 2),
                "remaining_reserve_after": round(remaining_reserve - estimated_hours_lost, 2),
            }
        return None

    def hours_per_lifeload_point(self, weekly_capacity: float) -> float:
        """
        Derived directly from the frozen LifeLoad formula: the
        CommitmentRatio term contributes LIFELOAD_WEIGHT_COMMITMENT_RATIO
        (0.30) of a 100-point scale, i.e. a full 0-to-1 swing in
        CommitmentRatio moves LifeLoad by (0.30 * 100) = 30 points. So one
        LifeLoad point from that term corresponds to
        (1 / 30) of a CommitmentRatio point, which converts to hours via
        Weekly Capacity (since CommitmentRatio = Commitment / WeeklyCapacity).
        """
        points_per_full_ratio_swing = LIFELOAD_WEIGHT_COMMITMENT_RATIO * 100
        if points_per_full_ratio_swing == 0:
            return 0.0
        return weekly_capacity / points_per_full_ratio_swing

    def try_lifeload_renegotiation(
        self,
        shortfall_hours: float,
        current_effective_lifeload: float,
        weekly_capacity: float,
        increase_points_used_this_week: float,
    ) -> dict | None:
        """
        Stage 2. Computes whether a small, capped LifeLoad increase can
        cover the remaining shortfall after Stage 1. Returns the proposal
        (points needed, hours unlocked) if it fits within BOTH the
        per-week points cap AND the absolute LifeLoad ceiling — never
        automatically applied, the orchestrator still requires approval
        before writing it to Shared State.
        """
        hours_per_point = self.hours_per_lifeload_point(weekly_capacity)
        if hours_per_point <= 0:
            return None

        headroom_by_cap = STAGE2_MAX_LIFELOAD_INCREASE_POINTS_PER_WEEK - increase_points_used_this_week
        headroom_by_ceiling = STAGE2_LIFELOAD_CEILING - current_effective_lifeload
        available_points = max(0.0, min(headroom_by_cap, headroom_by_ceiling))
        available_hours = available_points * hours_per_point

        if available_hours < shortfall_hours:
            return None  # Stage 2 can't fully cover it either -> Stage 3

        needed_points = round(shortfall_hours / hours_per_point, 2)
        return {
            "lifeload_increase_points": needed_points,
            "hours_unlocked": round(needed_points * hours_per_point, 2),
            "new_effective_lifeload": round(current_effective_lifeload + needed_points, 2),
        }
