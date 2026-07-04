"""
DoneHo — core data models (Build Brief, Section 4).
Pydantic models used both as the persistence shape AND as ADK
output_schema targets for structured agent output where noted.
"""

from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GoalCategory(str, Enum):
    STUDY_AND_LEARNING = "Study and Learning"
    CAREER_AND_WORK = "Career and Work"
    HEALTH_AND_WELLNESS = "Health and Wellness"
    FAMILY_AND_CHILDCARE = "Family and Childcare"
    FINANCIAL_PLANNING = "Financial Planning"
    LIFE_SKILLS_AND_IMPROVEMENT = "Life Skills and Improvement"
    RELATIONSHIPS_AND_SOCIAL = "Relationships and Social"
    HOME_AND_HOUSEHOLD = "Home and Household"
    LEISURE_AND_RECREATION = "Leisure and Recreation"
    SPIRITUAL_AND_MINDFULNESS = "Spiritual and Mindfulness"


class FocusLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class CommitmentTier(str, Enum):
    AGGRESSIVE = "Aggressive"
    NORMAL = "Normal"
    BALANCED = "Balanced"
    CONSERVATIVE = "Conservative"
    SURVIVAL = "Survival"


class RecoveryStep(str, Enum):
    STRETCH_REMAINING_DAYS = "stretch_remaining_days"
    REDUCE_SPRINT_SCOPE = "reduce_sprint_scope"
    EXTEND_MILESTONE_NEXT_WEEK = "extend_milestone_next_week"
    REDUCE_OR_DROP_GOAL = "reduce_or_drop_goal"


class DisruptionDirection(str, Enum):
    LOSS = "loss"   # costs time
    GAIN = "gain"   # frees up time


class AbsorptionOutcome(str, Enum):
    """Which stage of the staged absorption flow resolved a LOSS disruption
    (Proposed Enhancements, Entry 1)."""
    SILENT_ABSORPTION = "silent_absorption"          # Stage 1 — no approval needed
    LIFELOAD_RENEGOTIATION = "lifeload_renegotiation"  # Stage 2 — approval needed
    HIERARCHY_RECOVERY = "hierarchy_recovery"          # Stage 3, flexible task — approval needed
    ACCEPTED_AS_LOST = "accepted_as_lost"              # Stage 3, rigid task — approval needed


# ---------------------------------------------------------------------------
# Profile / User
# ---------------------------------------------------------------------------

class Profile(BaseModel):
    name: str
    profession: str

    # Optional, collected later, NOT wired into any formula (Section 8).
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None


class Task(BaseModel):
    id: str
    title: str
    clarified: bool = False
    clarification_note: Optional[str] = None
    is_flexible: bool = True  # postponable vs. time-locked (Section 7, Item 1)


class Goal(BaseModel):
    id: str
    category: GoalCategory
    traffic: float = Field(ge=0.0, le=1.0)
    volatility: float = Field(ge=0.0, le=1.0)
    tasks: List[Task] = Field(default_factory=list)
    focus_level: Optional[FocusLevel] = None  # set by DeterministicEngine


class Milestone(BaseModel):
    title: str
    expected_hours: float
    goal_id: str
    goal_title: str
    task_id: str
    task_title: str
    # --- Added for Entry 2 (Day Output) / Entry 3 (hierarchy mutation) ---
    # All optional with safe defaults so BlueprintAgent's existing
    # output_schema parsing is completely unaffected -- the agent never
    # sets these, DayOutputEngine and RecoveryApplier own writing them.
    completed: bool = False
    deferred: bool = False       # Stage 3 "extend_milestone_next_week"
    accepted_as_lost: bool = False  # Stage 3 "accepted as lost" (rigid task)


class DiagramStep(BaseModel):
    """One node in a rendered suggestion diagram (Section 6, visual mode)."""
    label: str
    order: int


class SuggestionItem(BaseModel):
    """
    Shared shape for Opportunity Map / Day Boosters / Smart Spend entries.
    Section 12.2: any numeric claim requires a one-line justification —
    enforced here as a required field, not optional prose.

    `link` and `diagram_steps` already existed. The fields below them are
    new, added so the frontend can show category-specific detail
    (a price and urgency for Smart Spend, a task pairing and difficulty
    for Opportunity Map, an action type for Day Boosters) that the mock
    frontend previously invented on its own. Optional and populated only
    where relevant -- never fabricated if the agent has no real value.
    """
    title: str
    description: str  # short, crisp (Section 6 brevity rule)
    technique: str     # which of the 15 techniques (Section 10) this uses
    time_saved_minutes: Optional[int] = None
    justification: Optional[str] = None  # required if time_saved_minutes is set

    action_type: Optional[str] = None  # Day Boosters: "youtube" | "app" | "tip"
    price: Optional[str] = None  # Smart Spend: e.g. "₹149" -- only if a real product was found
    urgency: Optional[str] = None  # Smart Spend: "Low" | "Medium" | "High"
    difficulty: Optional[str] = None  # Opportunity Map: "Easy" | "Medium" | "Hard"
    task1: Optional[str] = None  # Opportunity Map: first task in the pairing
    goal1: Optional[str] = None  # Opportunity Map: goal category of task1
    task2: Optional[str] = None  # Opportunity Map: second task in the pairing
    goal2: Optional[str] = None  # Opportunity Map: goal category of task2
    link: Optional[str] = None            # real link only, from google_search
    diagram_steps: Optional[List[DiagramStep]] = None  # visual mode, optional


class Blueprint(BaseModel):
    primary_goal: Optional[str] = None
    weekly_commitment_hours: float
    milestones: List[Milestone] = Field(default_factory=list)
    reserve_hours: float
    lifeload: float
    planning_confidence: float
    status: str = "draft"  # draft | committed
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionContract(BaseModel):
    """
    Owned exclusively by RecalibrationAgent, only after a disruption.
    Only created for Stage 2 / Stage 3 outcomes — Stage 1 (silent
    absorption) resolves without ever creating a contract, since it
    needs no approval (Proposed Enhancements, Entry 1).
    """
    original_blueprint_status: str
    outcome: AbsorptionOutcome
    recovery_step: Optional[RecoveryStep] = None  # only set for HIERARCHY_RECOVERY
    lifeload_increase_points: Optional[float] = None  # only set for LIFELOAD_RENEGOTIATION
    estimated_hours_lost: Optional[float] = None  # Entry 3 fix — needed to apply the mutation on approval
    affected_goal_id: Optional[str] = None
    affected_task_id: Optional[str] = None
    approved: bool = False
    notes: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DisruptionLog(BaseModel):
    description: str
    direction: DisruptionDirection = DisruptionDirection.LOSS
    estimated_hours: float
    day_of_week: str
    time_of_day: Optional[str] = None
    resolution_stage: Optional[AbsorptionOutcome] = None  # null for GAIN entries
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WeeklyPerformance(BaseModel):
    """One completed week's record, fed into ReviewEngine for PRF."""
    week_number: int
    completion_rate: float       # 0.0 - 1.0
    reserve_usage_ratio: float   # 0.0 - 1.0
    caregiving_hours: float = 0.0


class DailyCheckIn(BaseModel):
    """
    Entry 2 — Day Output. One evening's record: which of that day's
    expected milestones actually got done. Pre-ticked-complete by
    default in the UI; this stores what the user actually unticked.
    Aggregated across the week (see ReviewEngine feed in orchestrator)
    into a WeeklyPerformance record at week rollover -- this is what
    makes the PRF-earning loop real instead of manually-fed test data.
    """
    day_label: str  # e.g. "Monday", or an ISO date string
    expected_milestone_titles: List[str]
    missed_milestone_titles: List[str] = Field(default_factory=list)
    completion_rate: float  # (expected - missed) / expected, 0.0 if expected is empty
    life_happened_suggested: bool = False  # True if >50% missed (Entry 8 hook)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Agent output schemas (ADK output_schema targets)
# ---------------------------------------------------------------------------

class ClarificationFlag(BaseModel):
    task_id: str
    task_title: str
    is_ambiguous: bool
    question: Optional[str] = None  # only present if is_ambiguous


class ClarificationAgentOutput(BaseModel):
    flags: List[ClarificationFlag]


class BlueprintAgentOutput(BaseModel):
    milestones: List[Milestone]


class NudgeAgentOutput(BaseModel):
    opportunity_map: List[SuggestionItem]
    day_boosters: List[SuggestionItem]
    smart_spend: List[SuggestionItem]


class DisruptionCostEstimate(BaseModel):
    """
    Stage 0 output (Build Brief Section 6 last bullet) — the ONLY LLM call
    required for every LOSS disruption, regardless of which stage
    eventually resolves it. Also attempts to identify which task/goal the
    disruption relates to, since Stage 3 needs that to check is_flexible.
    If the disruption isn't tied to a specific task (e.g. a general
    schedule squeeze), both id fields are null and flexibility defaults
    to True in the orchestrator.
    """
    estimated_hours_lost: float
    affected_goal_id: Optional[str] = None
    affected_task_id: Optional[str] = None
    reasoning_note: str  # short internal justification, not shown raw to the user


class RecalibrationHierarchyOutput(BaseModel):
    """
    Stage 3 output — only invoked when Stage 1 (silent absorption) and
    Stage 2 (LifeLoad renegotiation) both fail to fully cover the
    disruption, AND the affected task is flexible. Uses the cost already
    estimated in Stage 0 rather than re-estimating.
    """
    chosen_step: RecoveryStep
    affected_goal_id: Optional[str] = None
    affected_task_id: Optional[str] = None
    needs_tiebreak_input: bool = False
    proposal_message: str  # calm, no guilt language, no "reserve" mentions


class RecalibrationProposal(BaseModel):
    """
    Unified result of processing one LOSS disruption, regardless of which
    stage resolved it. This is what the orchestrator hands back to the
    caller/UI — a single consistent shape whether it was auto-resolved
    (Stage 1) or is pending approval (Stage 2/3).
    """
    outcome: AbsorptionOutcome
    estimated_hours_lost: float
    lifeload_increase_points: Optional[float] = None
    chosen_step: Optional[RecoveryStep] = None
    affected_goal_id: Optional[str] = None
    affected_task_id: Optional[str] = None
    needs_tiebreak_input: bool = False
    requires_approval: bool  # False only for SILENT_ABSORPTION
    message: str  # calm, no guilt language, no "reserve" mentions


class FreeTimeSuggestionOutput(BaseModel):
    """
    Entry 9 — positive disruption (GAIN) handling. Routed to Nudge Agent,
    not Recalibration, since a loss-oriented recovery hierarchy makes no
    sense for freed-up time.
    """
    estimated_free_hours: float
    message: str  # short, warm acknowledgment — no guilt/loss framing
    suggestions: List[SuggestionItem]


class AetherTipOutput(BaseModel):
    """
    Entry 5 — Proactive Aether Presence. One short, timely, contextual
    observation, generated fresh from current state — never a canned
    string. May optionally use location (via the location sub-agent,
    AgentTool pattern, same constraint as google_search) if the user's
    profile has one set.
    """
    tip: str  # short, crisp, everyday English — same brevity rule as everywhere else
    used_location: bool = False


class AetherChatOutput(BaseModel):
    """
    Frontend-driven, free-form conversational turn with Aether — distinct
    from the proactive, unprompted AetherTipOutput above. The user asks
    something in their own words; Aether answers grounded in this
    session's real state (goals, blueprint, LifeLoad, recent disruptions).
    Same hard rules as every other user-facing message: never mention
    "reserve"/"buffer"/any hidden-capacity number, no guilt language.
    """
    reply: str
