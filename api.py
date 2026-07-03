"""
DoneHo — FastAPI layer wrapping DoneHoOrchestrator for the Lovable frontend.

This file is PURELY ADDITIVE. It does not modify orchestrator.py, engines/,
agents/, core/, or models/schemas.py — it translates HTTP requests into the
exact same orchestrator method calls main.py's CLI demo already uses.

Run:
    pip install fastapi uvicorn
    uvicorn api:app --reload --port 8000

Session model: one DoneHoOrchestrator instance per browser session, held
in memory (SESSIONS dict). Fine for a capstone demo / single-instance
deployment. Swap for a real session store (Redis, DB) only if this needs
to survive server restarts or run behind multiple instances.

CORS: set DONEHO_ALLOWED_ORIGINS to a comma-separated list of your
Lovable app's URL(s) before deploying anywhere real. Defaults to "*" for
local demo convenience.
"""

import os
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models.schemas import Profile, Goal, Task, GoalCategory, DisruptionDirection
from orchestrator import DoneHoOrchestrator, new_goal_id, new_task_id

app = FastAPI(title="DoneHo API")

_allowed_origins = os.getenv("DONEHO_ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allowed_origins == "*" else _allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Session store (in-memory; see module docstring) ---
SESSIONS: dict[str, DoneHoOrchestrator] = {}


def get_orchestrator(session_id: str) -> DoneHoOrchestrator:
    orchestrator = SESSIONS.get(session_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Session not found. Call /session/start first.")
    return orchestrator


# ---------------------------------------------------------------------------
# Request schemas — API boundary only. Deliberately simpler than the domain
# models in models/schemas.py: the client sends titles/values, the API
# generates ids server-side via new_goal_id()/new_task_id().
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    name: str
    profession: str


class StartSessionResponse(BaseModel):
    session_id: str


class TaskInput(BaseModel):
    title: str
    is_flexible: bool = True


class GoalInput(BaseModel):
    category: GoalCategory
    traffic: float = Field(ge=0.0, le=1.0)
    volatility: float = Field(ge=0.0, le=1.0)
    tasks: list[TaskInput] = []


class SubmitGoalsRequest(BaseModel):
    session_id: str
    goals: list[GoalInput]


class ClarifyRequest(BaseModel):
    session_id: str
    answers: dict[str, str]  # {task_id: user's free-text answer}


class Pass2Request(BaseModel):
    session_id: str
    caregiving_hours: float = 0.0
    planned_event_hours: float = 0.0
    other_time_constraint_hours: float = 0.0
    sleep_hours_override: Optional[float] = None
    commute_hours_override: Optional[float] = None
    work_hours_override: Optional[float] = None


class SessionOnlyRequest(BaseModel):
    session_id: str


class DisruptionRequest(BaseModel):
    session_id: str
    description: str
    direction: DisruptionDirection = DisruptionDirection.LOSS


class ModifyTaskRequest(BaseModel):
    session_id: str
    goal_id: str
    action: str  # "add" | "edit" | "remove"
    task_id: Optional[str] = None  # required for edit/remove
    title: Optional[str] = None    # required for add/edit
    is_flexible: bool = True


class ModifyGoalRequest(BaseModel):
    session_id: str
    action: str  # "add" | "remove"
    goal_id: Optional[str] = None            # required for remove
    category: Optional[GoalCategory] = None  # required for add
    traffic: Optional[float] = None
    volatility: Optional[float] = None


class DayOutputRequest(BaseModel):
    session_id: str
    day_label: str  # e.g. "Monday" or an ISO date string
    unticked_indices: list[int] = []  # positions from GET /day-output/checklist the user unticked


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _serialize_goal(goal: Goal) -> dict:
    return {
        "id": goal.id,
        "category": goal.category.value,
        "traffic": goal.traffic,
        "volatility": goal.volatility,
        "focus_level": goal.focus_level.value if goal.focus_level else None,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "clarified": t.clarified,
                "clarification_note": t.clarification_note,
                "is_flexible": t.is_flexible,
            }
            for t in goal.tasks
        ],
    }


def _serialize_blueprint(blueprint) -> Optional[dict]:
    if blueprint is None:
        return None
    return {
        "status": blueprint.status,
        "weekly_commitment_hours": blueprint.weekly_commitment_hours,
        "planning_confidence": blueprint.planning_confidence,
        "milestones": [
            {
                "title": m.title,
                "expected_hours": m.expected_hours,
                "goal_id": m.goal_id,
                "goal_title": m.goal_title,
                "task_id": m.task_id,
                "task_title": m.task_title,
                "completed": m.completed,
                "deferred": m.deferred,
                "accepted_as_lost": m.accepted_as_lost,
            }
            for m in blueprint.milestones
        ],
        # NOTE: reserve_hours is deliberately never included here — the
        # term and the number must never reach the frontend (Build Brief,
        # Section 6). If you're tempted to add it for a debug view, don't;
        # log it server-side instead.
    }


def _pending_clarifications(orchestrator: DoneHoOrchestrator) -> list[dict]:
    return [
        {"task_id": t.id, "task_title": t.title, "question": t.clarification_note}
        for g in orchestrator.state.goals
        for t in g.tasks
        if not t.clarified
    ]


def _dashboard_snapshot(orchestrator: DoneHoOrchestrator) -> dict:
    state = orchestrator.state
    return {
        "profile": {"name": state.profile.name, "profession": state.profile.profession},
        "goals": [_serialize_goal(g) for g in state.goals],
        "lifeload": state.effective_lifeload,
        "planning_confidence": state.planning_confidence,
        "weekly_capacity": state.weekly_capacity,
        "commitment_contract": state.commitment_contract,
        "blueprint": _serialize_blueprint(state.blueprint),
        "suggestions": {
            "opportunity_map": [s.model_dump() for s in state.suggestions["opportunity_map"]],
            "day_boosters": [s.model_dump() for s in state.suggestions["day_boosters"]],
            "smart_spend": [s.model_dump() for s in state.suggestions["smart_spend"]],
        },
        "pending_recalibration": (
            {
                "outcome": state.last_disruption_outcome.outcome.value,
                "message": state.last_disruption_outcome.message,
                "requires_approval": state.last_disruption_outcome.requires_approval,
                "needs_tiebreak_input": state.last_disruption_outcome.needs_tiebreak_input,
            }
            if state.last_disruption_outcome is not None
            else None
        ),
        "last_gain_suggestions": (
            state.last_gain_suggestions.model_dump()
            if state.last_gain_suggestions is not None
            else None
        ),
        "pending_clarifications": _pending_clarifications(orchestrator),
    }


# ---------------------------------------------------------------------------
# Endpoints — one per Lovable screen/action (see README table)
# ---------------------------------------------------------------------------

@app.post("/session/start", response_model=StartSessionResponse)
def start_session(req: StartSessionRequest):
    profile = Profile(name=req.name, profession=req.profession)
    orchestrator = DoneHoOrchestrator(profile)
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = orchestrator
    return StartSessionResponse(session_id=session_id)


@app.post("/goals")
def submit_goals(req: SubmitGoalsRequest):
    orchestrator = get_orchestrator(req.session_id)

    goals = [
        Goal(
            id=new_goal_id(),
            category=g.category,
            traffic=g.traffic,
            volatility=g.volatility,
            tasks=[Task(id=new_task_id(), title=t.title, is_flexible=t.is_flexible) for t in g.tasks],
        )
        for g in req.goals
    ]

    try:
        orchestrator.submit_goals(goals)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Clarification Agent call failed: {e}")

    return {
        "pending_clarifications": _pending_clarifications(orchestrator),
        "blueprint": _serialize_blueprint(orchestrator.state.blueprint),
        "goals": [_serialize_goal(g) for g in orchestrator.state.goals],
    }


@app.post("/clarify")
def clarify(req: ClarifyRequest):
    orchestrator = get_orchestrator(req.session_id)
    try:
        orchestrator.answer_clarifications(req.answers)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blueprint Agent call failed: {e}")
    return {"blueprint": _serialize_blueprint(orchestrator.state.blueprint)}


@app.post("/pass2")
def submit_pass2(req: Pass2Request):
    orchestrator = get_orchestrator(req.session_id)
    try:
        orchestrator.submit_pass2(
            caregiving_hours=req.caregiving_hours,
            planned_event_hours=req.planned_event_hours,
            other_time_constraint_hours=req.other_time_constraint_hours,
            sleep_hours_override=req.sleep_hours_override,
            commute_hours_override=req.commute_hours_override,
            work_hours_override=req.work_hours_override,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blueprint regeneration failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.post("/commit")
def commit(req: SessionOnlyRequest):
    orchestrator = get_orchestrator(req.session_id)
    try:
        orchestrator.commit_blueprint()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Nudge Agent call failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.post("/nudge/regenerate")
def regenerate(req: SessionOnlyRequest):
    orchestrator = get_orchestrator(req.session_id)
    try:
        orchestrator.regenerate_suggestions()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Nudge Agent call failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.post("/disruption")
def disruption(req: DisruptionRequest):
    orchestrator = get_orchestrator(req.session_id)
    try:
        orchestrator.report_disruption(req.description, req.direction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Recalibration/Nudge Agent call failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.post("/disruption/approve")
def approve_disruption(req: SessionOnlyRequest):
    orchestrator = get_orchestrator(req.session_id)
    try:
        orchestrator.approve_recalibration()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Approval cascade failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.post("/modify-task")
def modify_task(req: ModifyTaskRequest):
    orchestrator = get_orchestrator(req.session_id)

    if req.action == "add":
        if not req.title:
            raise HTTPException(status_code=400, detail="title is required to add a task.")
        task = Task(id=new_task_id(), title=req.title, is_flexible=req.is_flexible)
    elif req.action in ("edit", "remove"):
        if not req.task_id:
            raise HTTPException(status_code=400, detail="task_id is required to edit or remove a task.")
        task = Task(id=req.task_id, title=req.title or "", is_flexible=req.is_flexible)
    else:
        raise HTTPException(status_code=400, detail="action must be 'add', 'edit', or 'remove'.")

    try:
        orchestrator.modify_task(req.goal_id, task, req.action)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Blueprint regeneration failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.post("/modify-goal")
def modify_goal(req: ModifyGoalRequest):
    orchestrator = get_orchestrator(req.session_id)

    if req.action == "add":
        if req.category is None or req.traffic is None or req.volatility is None:
            raise HTTPException(
                status_code=400,
                detail="category, traffic, and volatility are required to add a goal.",
            )
        goal = Goal(id=new_goal_id(), category=req.category, traffic=req.traffic, volatility=req.volatility)
    elif req.action == "remove":
        if not req.goal_id:
            raise HTTPException(status_code=400, detail="goal_id is required to remove a goal.")
        # Only .id matters for removal — category/traffic/volatility are
        # placeholders, never read by orchestrator.modify_goal's remove path.
        goal = Goal(id=req.goal_id, category=GoalCategory.STUDY_AND_LEARNING, traffic=0, volatility=0)
    else:
        raise HTTPException(status_code=400, detail="action must be 'add' or 'remove'.")

    try:
        orchestrator.modify_goal(goal, req.action)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LifeLoad/Blueprint regeneration failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.get("/day-output/checklist")
def get_day_output_checklist(session_id: str):
    """Entry 2 -- today's pre-ticked checklist. Frontend renders every
    item as checked by default; the user unticks whatever was missed
    and submits via POST /day-output with those indices."""
    orchestrator = get_orchestrator(session_id)
    try:
        return {"checklist": orchestrator.get_day_output_checklist()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to build Day Output checklist: {e}")


@app.post("/day-output")
def submit_day_output(req: DayOutputRequest):
    """Entry 2 -- evening submission. Marks kept items complete, logs
    what was missed, feeds this week's running PRF totals, and flags
    should_offer_life_happened if the user missed more than half."""
    orchestrator = get_orchestrator(req.session_id)
    try:
        result = orchestrator.submit_day_output(req.day_label, set(req.unticked_indices))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Day Output submission failed: {e}")
    return {**result, **_dashboard_snapshot(orchestrator)}


@app.post("/life-happened")
def life_happened(req: SessionOnlyRequest):
    """Entry 8 -- no-reason-needed trigger. Only valid after at least one
    Day Output submission today (that's where the missed-hours cost
    comes from -- no LLM cost-estimation call needed, unlike the
    text-based /disruption endpoint)."""
    orchestrator = get_orchestrator(req.session_id)
    try:
        orchestrator.trigger_life_happened()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Life Happened flow failed: {e}")
    return _dashboard_snapshot(orchestrator)


@app.get("/aether-tip")
def aether_tip(session_id: str):
    """Entry 5 -- a fresh, state-aware proactive Aether line. Call this
    anytime the frontend wants to refresh Aether's comment (Dashboard
    load, after committing a Blueprint, etc)."""
    orchestrator = get_orchestrator(session_id)
    try:
        result = orchestrator.request_aether_tip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Aether Presence Agent call failed: {e}")
    return result.model_dump()


@app.post("/week/start")
def start_new_week(req: SessionOnlyRequest):
    """Call at week rollover — records this week's real WeeklyPerformance
    (Entry 2) into ReviewEngine, then resets Entry-1 running counters.
    is_first_week is managed internally by start_new_week() itself based
    on whether real performance data existed -- do not override it here."""
    orchestrator = get_orchestrator(req.session_id)
    orchestrator.start_new_week()
    return {"status": "new week started", "is_first_week": orchestrator.state.is_first_week}


@app.get("/state")
def get_state(session_id: str):
    orchestrator = get_orchestrator(session_id)
    return _dashboard_snapshot(orchestrator)


@app.get("/health")
def health():
    return {"status": "ok"}
