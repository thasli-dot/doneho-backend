"""
SharedExecutionState — single source of truth object (Build Brief, Section 3.2).

Critical rule: ONE WRITER PER FIELD. No two components may write to the
same field. Ownership map:
    DeterministicEngine owns: weekly_capacity, prf, lifeload, reserve_hours,
                               planning_confidence, commitment_contract
    BlueprintAgent owns:      blueprint
    RecalibrationAgent owns:  execution_contract (only after a disruption)
    NudgeAgent owns:          interaction_signals, suggestions
    (orchestrator owns:       profile, goals, disruption_log, week_number —
     these are set once during onboarding / user input, not computed)

This class enforces ownership at runtime: each field can only be written
via its designated setter, and each setter checks a caller tag so an
accidental cross-write raises immediately instead of silently corrupting
state. This is deliberately stricter than a plain dataclass would be,
because "one writer per field" is a frozen architectural invariant, not
just a convention to remember.
"""

from typing import Any, Optional
from models.schemas import (
    Profile, Goal, Blueprint, ExecutionContract, DisruptionLog,
    RecalibrationProposal, FreeTimeSuggestionOutput, DailyCheckIn,
)


class OwnershipViolation(Exception):
    """Raised when a component tries to write a field it doesn't own."""


class SharedExecutionState:
    # field_name -> owner tag
    _OWNERSHIP = {
        "weekly_capacity": "DeterministicEngine",
        "prf": "DeterministicEngine",
        "lifeload": "DeterministicEngine",
        "reserve_hours": "DeterministicEngine",
        "planning_confidence": "DeterministicEngine",
        "commitment_contract": "DeterministicEngine",
        "blueprint": "BlueprintAgent",
        "execution_contract": "RecalibrationAgent",
        "suggestions": "NudgeAgent",
        "interaction_signals": "NudgeAgent",
        # Entry 1 — staged silent absorption. NOTE: the *base* lifeload
        # value above stays DeterministicEngine-owned; these are a
        # separate running counter and delta, never a second writer to
        # the same field. See effective_lifeload property below.
        "reserve_used_this_week": "RecalibrationAgent",
        "lifeload_renegotiated_increase": "RecalibrationAgent",
        "last_disruption_outcome": "RecalibrationAgent",
        # Entry 9 — positive disruption (gain) handling.
        "last_gain_suggestions": "NudgeAgent",
    }

    def __init__(self, profile: Profile):
        self.profile = profile
        self.goals: list[Goal] = []
        self.is_first_week: bool = True
        self.week_number: int = 1

        # DeterministicEngine-owned
        self.weekly_capacity: float = 0.0
        self.prf: float = 0.0
        self.lifeload: float = 0.0
        self.reserve_hours: float = 0.0
        self.planning_confidence: float = 0.0
        self.commitment_contract: dict = {}

        # BlueprintAgent-owned
        self.blueprint: Optional[Blueprint] = None

        # RecalibrationAgent-owned
        self.execution_contract: Optional[ExecutionContract] = None
        # Entry 1 — running counters for the current week. Reset via
        # reset_weekly_counters() at week rollover (orchestrator lifecycle
        # operation, not a component write — see method docstring).
        self.reserve_used_this_week: float = 0.0
        self.lifeload_renegotiated_increase: float = 0.0
        # Transient — the most recent disruption's resolution, whichever
        # stage handled it. UI reads this to know what to show/animate.
        self.last_disruption_outcome: Optional[RecalibrationProposal] = None

        # NudgeAgent-owned
        self.suggestions: dict = {"opportunity_map": [], "day_boosters": [], "smart_spend": []}
        self.interaction_signals: list[dict] = []
        # Entry 9 — most recent gain-handling suggestions.
        self.last_gain_suggestions: Optional[FreeTimeSuggestionOutput] = None

        # Orchestrator-managed (set once from user input, not "computed")
        self.disruption_log: list[DisruptionLog] = []
        # Entry 2 — Day Output. One entry per day submitted, aggregated
        # into a WeeklyPerformance at week rollover (see orchestrator's
        # start_new_week). Orchestrator-managed, same as disruption_log.
        self.daily_checkins: list[DailyCheckIn] = []

        # --- Entry 2 (Day Output) — orchestrator-managed, same category as
        # disruption_log: accumulated raw input over the week, not a value
        # any single engine/agent computes and owns. Reset at week rollover.
        self.day_output_totals: dict = {"total_checked": 0, "total_missed": 0}

        # --- Entry 7 (per-user pattern learning) — last caregiving_hours
        # value seen via Pass 2, kept so week-end WeeklyPerformance can
        # record it without needing a fresh Pass 2 call at rollover time.
        self.last_caregiving_hours: float = 0.0

    def write(self, owner: str, field: str, value: Any) -> None:
        expected_owner = self._OWNERSHIP.get(field)
        if expected_owner is None:
            raise OwnershipViolation(f"'{field}' is not a registered Shared State field.")
        if expected_owner != owner:
            raise OwnershipViolation(
                f"'{owner}' attempted to write '{field}', which is owned by '{expected_owner}'."
            )
        setattr(self, field, value)

    @property
    def effective_lifeload(self) -> float:
        """
        Base LifeLoad (DeterministicEngine-owned, computed from the active
        goal set) plus any Stage-2 renegotiated increase approved this
        week. This is the number the Dashboard should display — never
        read `self.lifeload` alone once staged absorption is in play.
        """
        return round(self.lifeload + self.lifeload_renegotiated_increase, 2)

    @property
    def remaining_reserve(self) -> float:
        """Reserve Hours ceiling minus whatever's already been silently
        absorbed or renegotiated away this week. Floors at 0."""
        return round(max(self.reserve_hours - self.reserve_used_this_week, 0), 2)

    def reset_weekly_counters(self) -> None:
        """
        Week-rollover lifecycle operation, called by the orchestrator when
        a new week starts. This intentionally bypasses the write() gate:
        it isn't a component computing a value mid-week, it's the system
        resetting state between weeks — a different kind of operation
        than the one-writer-per-field rule is protecting against.

        NOTE (Entry 2): the orchestrator must aggregate self.daily_checkins
        into a WeeklyPerformance and call review_engine.record_week_performance()
        BEFORE calling this method — daily_checkins is cleared here as part
        of the same rollover, and that data would otherwise be lost.
        """
        self.reserve_used_this_week = 0.0
        self.lifeload_renegotiated_increase = 0.0
        self.last_disruption_outcome = None
        self.last_gain_suggestions = None
        self.daily_checkins = []
        self.day_output_totals = {"total_checked": 0, "total_missed": 0}

    def apply_deterministic_result(self, result: dict) -> None:
        """Convenience bulk-write used by the orchestrator right after
        DeterministicEngine.run() — still routes through write() so
        ownership is still enforced per field."""
        self.write("DeterministicEngine", "weekly_capacity", result["weekly_capacity"])
        self.write("DeterministicEngine", "prf", result["prf"])
        self.write("DeterministicEngine", "lifeload", result["lifeload"])
        self.write("DeterministicEngine", "reserve_hours", result["reserve_hours"])
        self.write("DeterministicEngine", "planning_confidence", result["planning_confidence"])
        self.write("DeterministicEngine", "commitment_contract", result["commitment"])
