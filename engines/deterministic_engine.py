"""
DeterministicEngine — orchestrates CapacityEngine, ReviewEngine,
CommitmentEngine, ReserveEngine, LifeLoadEngine.

This is the ONLY writer to these Shared State fields (Section 3.2):
Weekly Capacity, PRF, LifeLoad, Reserve Hours, Planning Confidence,
Commitment Contract. No AI/LLM calls happen anywhere in this file.
"""

from models.schemas import Goal, Profile
from engines.capacity_engine import CapacityEngine
from engines.review_engine import ReviewEngine
from engines.commitment_engine import CommitmentEngine
from engines.reserve_engine import ReserveEngine
from engines.lifeload_engine import LifeLoadEngine


class DeterministicEngine:
    def __init__(self):
        self.capacity_engine = CapacityEngine()
        self.review_engine = ReviewEngine()
        self.commitment_engine = CommitmentEngine()
        self.reserve_engine = ReserveEngine()
        self.lifeload_engine = LifeLoadEngine()

    def run(
        self,
        profile: Profile,
        goals: list[Goal],
        is_first_week: bool,
        sleep_hours_override: float | None = None,
        commute_hours_override: float | None = None,
        work_hours_override: float | None = None,
        caregiving_hours: float = 0.0,
        planned_event_hours: float = 0.0,
        other_time_constraint_hours: float = 0.0,
    ) -> dict:
        """
        Runs the full deterministic pipeline once and returns every value
        that Shared State's DeterministicEngine-owned fields need.
        """
        capacity_result = self.capacity_engine.calculate(
            profession=profile.profession,
            sleep_hours_override=sleep_hours_override,
            commute_hours_override=commute_hours_override,
            work_hours_override=work_hours_override,
            caregiving_hours=caregiving_hours,
            planned_event_hours=planned_event_hours,
            other_time_constraint_hours=other_time_constraint_hours,
        )
        weekly_capacity = capacity_result["weekly_capacity"]

        prf = self.review_engine.calculate_prf(current_caregiving_hours=caregiving_hours)

        commitment_result = self.commitment_engine.calculate(
            weekly_capacity=weekly_capacity, prf=prf, is_first_week=is_first_week
        )
        recommended_commitment = commitment_result["recommended_commitment"]

        reserve_hours = self.reserve_engine.calculate(
            weekly_capacity=weekly_capacity,
            recommended_commitment=recommended_commitment,
            is_first_week=is_first_week,
        )

        lifeload = self.lifeload_engine.calculate_lifeload(
            goals=goals,
            recommended_commitment=recommended_commitment,
            weekly_capacity=weekly_capacity,
        )

        confidence = self.lifeload_engine.calculate_confidence(
            prf=prf,
            reserve_hours=reserve_hours,
            weekly_capacity=weekly_capacity,
            lifeload=lifeload,
        )

        for g in goals:
            g.focus_level = self.lifeload_engine.classify_focus(g)

        hours_by_goal = self.lifeload_engine.allocate_hours_by_focus(goals, recommended_commitment)

        return {
            "capacity": capacity_result,
            "weekly_capacity": weekly_capacity,
            "prf": prf,
            "commitment": commitment_result,
            "recommended_commitment": recommended_commitment,
            "reserve_hours": reserve_hours,
            "lifeload": lifeload,
            "lifeload_over_threshold": self.lifeload_engine.is_over_safe_threshold(lifeload),
            "has_leisure_or_mindfulness": self.lifeload_engine.has_leisure_or_mindfulness(goals),
            "planning_confidence": confidence,
            "hours_by_goal": hours_by_goal,
        }
