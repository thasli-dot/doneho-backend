"""
AetherPresenceAgent (Proposed Enhancements, Entry 5).

A persistent assistant voice that proactively comments on the user's
CURRENT state -- not a fixed rotation of canned lines, a fresh
observation generated from real Shared State values each time it's
called (LifeLoad, leisure balance, upcoming milestones, recent
disruptions). Callable at any point the frontend wants a fresh Aether
line (Dashboard load, after committing a Blueprint, etc).

Location-aware suggestions only fire if Profile.location is set --
calls the location sub-agent (AgentTool pattern, agents/location_subagent.py)
first, then folds whatever it found into this agent's own reasoning,
same two-step pattern used for Smart Spend real links (Entry 4).
"""

import asyncio
import uuid

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from models.schemas import Goal, Blueprint, AetherTipOutput, GoalCategory
from core.agent_runner import run_agent_sync
from agents.location_subagent import build_location_subagent
from config import MODEL_NAME

INSTRUCTION = """You are Aether, DoneHo's calm, warm, ever-present guide.
Generate ONE short, timely, personality-driven observation about the
user's CURRENT week -- not a generic greeting.

You will be given: current LifeLoad, whether a leisure/mindfulness goal
exists this week, the Blueprint's current milestones, and how many
disruptions have been logged this week so far. You may also be given a
real, nearby location suggestion already found for the user -- if so,
you may naturally weave it in as ONE optional idea, never a demand. Set
used_location=true only if you actually included that suggestion.

Good observation patterns (illustrative only, don't copy verbatim):
- Noticing no leisure goal exists and gently flagging burnout risk
- Noticing LifeLoad is comfortably low and encouraging a bit more ambition
- Noticing several disruptions already this week and acknowledging it calmly
- Highlighting one specific upcoming milestone as a good next step

Hard rules (same as everywhere else in DoneHo):
- Short, crisp, everyday English. One or two sentences.
- NEVER mention "reserve", "buffer", or any hidden-capacity number.
- NEVER guilt-based language.
- Only mention a location idea that was actually found by the location
  tool -- never invent a place name yourself.

Return ONLY the structured output. No extra commentary."""


def build_aether_presence_agent() -> Agent:
    return Agent(
        name="aether_presence_agent",
        model=MODEL_NAME,
        description="Generates a fresh, state-aware proactive comment from Aether.",
        instruction=INSTRUCTION,
        output_schema=AetherTipOutput,
    )


def _has_leisure_or_mindfulness(goals: list[Goal]) -> bool:
    return any(
        g.category in (GoalCategory.LEISURE_AND_RECREATION, GoalCategory.SPIRITUAL_AND_MINDFULNESS)
        for g in goals
    )


def run_aether_tip(
    goals: list[Goal],
    blueprint: Blueprint | None,
    lifeload: float,
    disruptions_this_week: int,
    location: str | None = None,
) -> AetherTipOutput:
    location_note = ""
    if location:
        location_note = _find_location_idea(location)

    lines = [
        f"Current LifeLoad: {lifeload}",
        f"Has leisure/mindfulness goal this week: {_has_leisure_or_mindfulness(goals)}",
        f"Disruptions logged so far this week: {disruptions_this_week}",
    ]
    if blueprint is not None:
        active = [m for m in blueprint.milestones if not m.completed and not m.deferred and not m.accepted_as_lost]
        lines.append(f"Blueprint status: {blueprint.status}, {len(active)} active milestones remaining")
        for m in active[:5]:
            lines.append(f"  - {m.title} ({m.goal_title})")
    if location_note:
        lines.append(f"\nA real nearby idea already found for this user: {location_note}")

    prompt = "\n".join(lines)
    agent = build_aether_presence_agent()
    return run_agent_sync(agent, prompt, AetherTipOutput)


def _find_location_idea(location: str) -> str:
    """
    Calls the location sub-agent directly (plain text, no output_schema --
    it uses google_maps_grounding, which can't coexist with output_schema,
    same constraint as google_search). Failures here never block the main
    proactive comment -- Aether just comments without a location idea.
    """
    agent = build_location_subagent()
    prompt = (
        f"User's area: {location}. Suggest ONE real, nearby spot good for "
        f"a short refreshing break (a park, cafe, or similar)."
    )
    try:
        return asyncio.run(_run_agent_text_only(agent, prompt))
    except Exception:
        return ""


async def _run_agent_text_only(agent: Agent, prompt: str) -> str:
    session_service = InMemorySessionService()
    session_id = str(uuid.uuid4())
    await session_service.create_session(app_name="doneho", user_id="doneho_user", session_id=session_id)

    runner = Runner(agent=agent, app_name="doneho", session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    final_text = ""
    async for event in runner.run_async(user_id="doneho_user", session_id=session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""
    return final_text
