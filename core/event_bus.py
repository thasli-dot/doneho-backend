"""
EventBus — simple publish/subscribe (Build Brief, Section 3.3).
Agents never call each other directly — everything flows through events
and Shared State. Synchronous for simplicity; swap for an async queue
later if needed without changing any subscriber's interface.
"""

from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._log: list[tuple[str, dict]] = []  # simple audit trail, handy for demos

    def subscribe(self, event_name: str, handler: Callable) -> None:
        self._subscribers[event_name].append(handler)

    def publish(self, event_name: str, payload: dict | None = None) -> None:
        payload = payload or {}
        self._log.append((event_name, payload))
        for handler in self._subscribers.get(event_name, []):
            handler(payload)

    def event_log(self) -> list[tuple[str, dict]]:
        return list(self._log)


# --- Canonical event names used across the system ---
EVENT_GOALS_SUBMITTED = "goals_submitted"
EVENT_TASKS_CLARIFIED = "tasks_clarified"
EVENT_BLUEPRINT_REQUESTED = "blueprint_requested"
EVENT_BLUEPRINT_GENERATED = "blueprint_generated"
EVENT_BLUEPRINT_COMMITTED = "blueprint_committed"
EVENT_PASS2_SUBMITTED = "pass2_submitted"
EVENT_DISRUPTION_REPORTED = "disruption_reported"
EVENT_RECALIBRATION_PROPOSED = "recalibration_proposed"
EVENT_RECALIBRATION_APPROVED = "recalibration_approved"
EVENT_TASK_OR_GOAL_MODIFIED = "task_or_goal_modified"
EVENT_DAY_OUTPUT_SUBMITTED = "day_output_submitted"
EVENT_NUDGE_REFRESH_REQUESTED = "nudge_refresh_requested"
EVENT_LIFE_HAPPENED_REPORTED = "life_happened_reported"  # Entry 8
