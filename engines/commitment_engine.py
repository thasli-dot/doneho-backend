"""
CommitmentEngine — pure math, zero LLM calls (Build Brief, Section 5).

Recommended Commitment = Weekly Capacity x tier_factor(PRF)
Weekly Commitment Contract = a RANGE, not one number:
    min_hours = recommended * 0.85
    max_hours = min(recommended * 1.10, Weekly Capacity)
                -> capped at exactly `recommended` during a first-ever week
"""

from config import COMMITMENT_TIERS, COMMITMENT_MIN_FACTOR, COMMITMENT_MAX_FACTOR


class CommitmentEngine:
    def calculate(self, weekly_capacity: float, prf: float, is_first_week: bool) -> dict:
        tier_name, factor = self._tier_for_prf(prf)
        recommended = weekly_capacity * factor

        min_hours = recommended * COMMITMENT_MIN_FACTOR

        if is_first_week:
            max_hours = recommended
        else:
            max_hours = min(recommended * COMMITMENT_MAX_FACTOR, weekly_capacity)

        return {
            "tier": tier_name,
            "tier_factor": factor,
            "recommended_commitment": round(recommended, 2),
            "min_hours": round(min_hours, 2),
            "max_hours": round(max_hours, 2),
        }

    def _tier_for_prf(self, prf: float) -> tuple[str, float]:
        for min_prf, tier_name, factor in COMMITMENT_TIERS:
            if prf >= min_prf:
                return tier_name, factor
        # Should never reach here since COMMITMENT_TIERS bottoms out at 0.0
        return COMMITMENT_TIERS[-1][1], COMMITMENT_TIERS[-1][2]
