"""
ReviewEngine — tracks weekly performance history, calculates earned PRF
(Planning Reliability Factor). Pure math, zero LLM calls.

PRF rules (Build Brief, Section 5):
- First-ever week: neutral default 0.60
- Every week after, adjusted from the PREVIOUS week's actual performance:
    completion_rate >= 0.80 AND reserve_usage <= 0.30  -> PRF += 0.05
    completion_rate < 0.50  OR  reserve_usage >= 0.80   -> PRF -= 0.07
    otherwise                                            -> nudge 10% toward 0.5
- Clamp PRF between 0.1 and 1.0
- Caregiving reduces PRF slightly further (capped penalty, max -0.20)
"""

from models.schemas import WeeklyPerformance
from config import (
    PRF_FIRST_WEEK_DEFAULT,
    PRF_MIN,
    PRF_MAX,
    PRF_GOOD_COMPLETION_THRESHOLD,
    PRF_GOOD_RESERVE_USAGE_CEILING,
    PRF_GOOD_BONUS,
    PRF_BAD_COMPLETION_THRESHOLD,
    PRF_BAD_RESERVE_USAGE_FLOOR,
    PRF_BAD_PENALTY,
    PRF_NEUTRAL_TARGET,
    PRF_NEUTRAL_PULL_FRACTION,
    PRF_CAREGIVING_MAX_PENALTY,
)


class ReviewEngine:
    def __init__(self):
        self.history: list[WeeklyPerformance] = []

    def record_week_performance(self, performance: WeeklyPerformance) -> None:
        """Append a completed week's real performance data (from Day Output)."""
        self.history.append(performance)

    def calculate_prf(self, current_caregiving_hours: float = 0.0) -> float:
        if not self.history:
            prf = PRF_FIRST_WEEK_DEFAULT
        else:
            last = self.history[-1]
            # Start from the previous PRF if we have one stored, else neutral.
            prev_prf = getattr(self, "_last_prf", PRF_FIRST_WEEK_DEFAULT)

            if (
                last.completion_rate >= PRF_GOOD_COMPLETION_THRESHOLD
                and last.reserve_usage_ratio <= PRF_GOOD_RESERVE_USAGE_CEILING
            ):
                prf = prev_prf + PRF_GOOD_BONUS
            elif (
                last.completion_rate < PRF_BAD_COMPLETION_THRESHOLD
                or last.reserve_usage_ratio >= PRF_BAD_RESERVE_USAGE_FLOOR
            ):
                prf = prev_prf - PRF_BAD_PENALTY
            else:
                prf = prev_prf + (PRF_NEUTRAL_TARGET - prev_prf) * PRF_NEUTRAL_PULL_FRACTION

        # Caregiving penalty: capped, scales with caregiving hours.
        # Uses a simple saturating scale — 20+ caregiving hrs/week hits the cap.
        caregiving_penalty = min(
            PRF_CAREGIVING_MAX_PENALTY,
            (current_caregiving_hours / 20.0) * PRF_CAREGIVING_MAX_PENALTY,
        )
        prf -= caregiving_penalty

        prf = max(PRF_MIN, min(PRF_MAX, prf))
        self._last_prf = prf
        return round(prf, 4)

    def get_prf_trend(self) -> str | None:
        """Returns a trend label if >=2 weeks of history exist, else None
        (Dashboard must omit the trend element entirely otherwise)."""
        if len(self.history) < 2:
            return None
        recent = self.history[-1].completion_rate
        prior = self.history[-2].completion_rate
        if recent > prior:
            return "trending up"
        if recent < prior:
            return "trending down"
        return "stable"
