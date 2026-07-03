"""
LifeLoad calculator — pure math, zero LLM calls (Build Brief, Section 5).

LifeLoad = 100 x (0.35*avg_Traffic + 0.35*avg_Volatility + 0.30*CommitmentRatio)
CommitmentRatio = Recommended Commitment / Weekly Capacity

Planning Confidence = 100 x (0.4*PRF + 0.3*ReserveRatio + 0.3*(1 - LifeLoad/100))
ReserveRatio = Reserve Hours / Weekly Capacity

Goal Focus Classification:
FocusScore = 0.65*Traffic + 0.35*Volatility
  >= 0.66 -> High, >= 0.33 -> Medium, else Low

LifeLoad is fixed for the whole week once calculated — no change without
the explicit staged mechanism (Section 7, Item 2). This engine just
computes the number; enforcing "no silent change" is the orchestrator's job.
"""

from models.schemas import Goal, FocusLevel
from config import (
    LIFELOAD_WEIGHT_TRAFFIC,
    LIFELOAD_WEIGHT_VOLATILITY,
    LIFELOAD_WEIGHT_COMMITMENT_RATIO,
    LIFELOAD_SAFE_THRESHOLD,
    CONFIDENCE_WEIGHT_PRF,
    CONFIDENCE_WEIGHT_RESERVE_RATIO,
    CONFIDENCE_WEIGHT_LIFELOAD_INVERSE,
    FOCUS_WEIGHT_TRAFFIC,
    FOCUS_WEIGHT_VOLATILITY,
    FOCUS_HIGH_THRESHOLD,
    FOCUS_MEDIUM_THRESHOLD,
)


class LifeLoadEngine:
    def calculate_lifeload(
        self, goals: list[Goal], recommended_commitment: float, weekly_capacity: float
    ) -> float:
        if not goals:
            avg_traffic = 0.0
            avg_volatility = 0.0
        else:
            avg_traffic = sum(g.traffic for g in goals) / len(goals)
            avg_volatility = sum(g.volatility for g in goals) / len(goals)

        commitment_ratio = (
            recommended_commitment / weekly_capacity if weekly_capacity > 0 else 0.0
        )

        lifeload = 100 * (
            LIFELOAD_WEIGHT_TRAFFIC * avg_traffic
            + LIFELOAD_WEIGHT_VOLATILITY * avg_volatility
            + LIFELOAD_WEIGHT_COMMITMENT_RATIO * commitment_ratio
        )
        return round(min(max(lifeload, 0), 100), 2)

    def is_over_safe_threshold(self, lifeload: float) -> bool:
        return lifeload > LIFELOAD_SAFE_THRESHOLD

    def has_leisure_or_mindfulness(self, goals: list[Goal]) -> bool:
        from models.schemas import GoalCategory

        return any(
            g.category in (GoalCategory.LEISURE_AND_RECREATION, GoalCategory.SPIRITUAL_AND_MINDFULNESS)
            for g in goals
        )

    def calculate_confidence(self, prf: float, reserve_hours: float, weekly_capacity: float, lifeload: float) -> float:
        reserve_ratio = reserve_hours / weekly_capacity if weekly_capacity > 0 else 0.0

        confidence = 100 * (
            CONFIDENCE_WEIGHT_PRF * prf
            + CONFIDENCE_WEIGHT_RESERVE_RATIO * reserve_ratio
            + CONFIDENCE_WEIGHT_LIFELOAD_INVERSE * (1 - lifeload / 100)
        )
        return round(min(max(confidence, 0), 100), 2)

    def classify_focus(self, goal: Goal) -> FocusLevel:
        score = FOCUS_WEIGHT_TRAFFIC * goal.traffic + FOCUS_WEIGHT_VOLATILITY * goal.volatility
        if score >= FOCUS_HIGH_THRESHOLD:
            return FocusLevel.HIGH
        if score >= FOCUS_MEDIUM_THRESHOLD:
            return FocusLevel.MEDIUM
        return FocusLevel.LOW

    def allocate_hours_by_focus(self, goals: list[Goal], total_hours: float) -> dict[str, float]:
        """
        Splits total weekly commitment hours across goals proportional to
        focus level. High gets the most, Low gets the least but never zero.
        """
        weight_map = {FocusLevel.HIGH: 3, FocusLevel.MEDIUM: 2, FocusLevel.LOW: 1}
        weights = {}
        for g in goals:
            focus = g.focus_level or self.classify_focus(g)
            weights[g.id] = weight_map[focus]

        total_weight = sum(weights.values()) or 1
        return {
            goal_id: round(total_hours * (w / total_weight), 2)
            for goal_id, w in weights.items()
        }
