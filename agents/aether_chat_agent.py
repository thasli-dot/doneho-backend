"""
AetherChatAgent (added for real frontend<->backend wiring).

Distinct from aether_presence_agent.py: that one is PROACTIVE (Aether
speaks first, unprompted). This one is REACTIVE — the user typed a
free-form message in the frontend's Aether chat panel, and Aether
answers it, grounded in the real Shared Execution State for this
session (never inventing numbers, never guessing at goals/milestones
the user didn't actually set).

Kept as its own small agent (rather than folded into Presence) for the
same reason every other DoneHo agent stays narrow: a proactive comment
and a reactive answer are different jobs with different failure modes,
and mixing them would blur which one a given call is exercising.
"""

from models.schemas import Goal, Blueprint, AetherChatOutput
from core.agent_runner import run_agent_sync
from config import MODEL_NAME
from google.adk.agents import Agent

INSTRUCTION = """You are Aether, DoneHo's calm, warm, ever-present guide.
The user just asked or said something in the chat panel. Reply directly
to what they said, in one to three short sentences, grounded ONLY in
the real state given to you below (their actual goals, blueprint
milestones, LifeLoad, and recent disruptions) — never invent a goal,
milestone, or number that isn't in that state.

Hard rules (same as everywhere else in DoneHo):
- Short, crisp, everyday English.
- NEVER mention "reserve", "buffer", or any hidden-capacity number.
- NEVER guilt-based language, ever, even if the user is venting about
  falling behind.
- If the user asks something with no real answer in the given state
  (e.g. a medical or financial question), gently decline and redirect
  to the relevant part of the app instead of guessing.

Return ONLY the structured output. No extra commentary."""


def build_aether_chat_agent() -> Agent:
    return Agent(
        name="aether_chat_agent",
        model=MODEL_NAME,
        description="Answers a free-form user chat message, grounded in real session state.",
        instruction=INSTRUCTION,
        output_schema=AetherChatOutput,
    )


def run_aether_chat(
    user_message: str,
    goals: list[Goal],
    blueprint: Blueprint | None,
    lifeload: float,
    disruptions_this_week: int,
    recent_history: list[dict] | None = None,
) -> AetherChatOutput:
    lines = [
        f"Current LifeLoad: {lifeload}",
        f"Disruptions logged so far this week: {disruptions_this_week}",
    ]
    if blueprint is not None:
        active = [m for m in blueprint.milestones if not m.completed and not m.deferred and not m.accepted_as_lost]
        lines.append(f"Blueprint status: {blueprint.status}, {len(active)} active milestones remaining")
        for m in active[:8]:
            lines.append(f"  - {m.title} ({m.goal_title})")
    else:
        lines.append("No blueprint committed yet.")

    if recent_history:
        lines.append("\nRecent conversation (oldest first):")
        for turn in recent_history[-6:]:
            lines.append(f"  {turn['role']}: {turn['content']}")

    lines.append(f"\nUser's new message: {user_message}")

    prompt = "\n".join(lines)
    agent = build_aether_chat_agent()
    return run_agent_sync(agent, prompt, AetherChatOutput)
