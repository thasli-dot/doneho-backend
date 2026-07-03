"""
CapacityEngine — pure math, zero AI/LLM calls (Build Brief, Section 3.1, 5).

Weekly Capacity (WC):
    WC = 168 - Sleep - Fixed Work - Commute - Personal Care
             - Caregiving - Planned Events - Other

Includes the safety clamp: no single onboarding answer category may
consume more than SAFETY_CLAMP_FRACTION of what's left after fixed
essentials (sleep, work, commute, personal care).
"""

from data.profession_defaults import get_profession_defaults
from config import (
    HOURS_PER_WEEK,
    DEFAULT_SLEEP_HOURS,
    DEFAULT_PERSONAL_CARE_HOURS,
    SAFETY_CLAMP_FRACTION,
)


class CapacityEngine:
    def calculate(
        self,
        profession: str,
        sleep_hours_override: float | None = None,
        commute_hours_override: float | None = None,
        work_hours_override: float | None = None,
        caregiving_hours: float = 0.0,
        planned_event_hours: float = 0.0,
        other_time_constraint_hours: float = 0.0,
    ) -> dict:
        default_work, default_commute = get_profession_defaults(profession)

        sleep = sleep_hours_override if sleep_hours_override is not None else DEFAULT_SLEEP_HOURS
        work = work_hours_override if work_hours_override is not None else default_work
        commute = commute_hours_override if commute_hours_override is not None else default_commute
        personal_care = DEFAULT_PERSONAL_CARE_HOURS

        fixed_essentials = sleep + work + commute + personal_care
        remaining_before_variable = max(HOURS_PER_WEEK - fixed_essentials, 0)

        # Safety clamp: caregiving + events + other cannot exceed
        # SAFETY_CLAMP_FRACTION of what's left — scale proportionally if so.
        variable_total = caregiving_hours + planned_event_hours + other_time_constraint_hours
        clamp_ceiling = remaining_before_variable * SAFETY_CLAMP_FRACTION

        if variable_total > clamp_ceiling and variable_total > 0:
            scale = clamp_ceiling / variable_total
            caregiving_hours *= scale
            planned_event_hours *= scale
            other_time_constraint_hours *= scale
            variable_total = clamp_ceiling

        weekly_capacity = max(
            HOURS_PER_WEEK
            - sleep
            - work
            - commute
            - personal_care
            - caregiving_hours
            - planned_event_hours
            - other_time_constraint_hours,
            0,
        )

        return {
            "weekly_capacity": round(weekly_capacity, 2),
            "sleep_hours": sleep,
            "work_hours": work,
            "commute_hours": commute,
            "personal_care_hours": personal_care,
            "caregiving_hours": round(caregiving_hours, 2),
            "planned_event_hours": round(planned_event_hours, 2),
            "other_time_constraint_hours": round(other_time_constraint_hours, 2),
            "clamp_applied": variable_total >= clamp_ceiling and clamp_ceiling > 0,
        }
