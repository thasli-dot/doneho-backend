"""
ReserveEngine — pure math, zero LLM calls (Build Brief, Section 5).

Reserve = Weekly Capacity - Recommended Commitment
First-ever week: +15% wider safety buffer (no history yet).
Floor at 0, never negative.

CRITICAL: the term "Reserve Hours" and its specific number must NEVER be
shown to the user directly (Section 6). This engine only computes the
number for internal use by DeterministicEngine / RecalibrationAgent.
"""

from config import RESERVE_FIRST_WEEK_BOOST


class ReserveEngine:
    def calculate(self, weekly_capacity: float, recommended_commitment: float, is_first_week: bool) -> float:
        reserve = weekly_capacity - recommended_commitment

        if is_first_week:
            reserve *= 1 + RESERVE_FIRST_WEEK_BOOST

        return round(max(reserve, 0), 2)
