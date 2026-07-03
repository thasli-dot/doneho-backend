"""
Location sub-agent (Build Brief, Section 7 Item 6 / Roadmap Entry 5).
ADK's built-in `google_maps_grounding` tool has the same constraint as
`google_search`: it cannot be combined with `output_schema` on the same
agent. Same fix as search_subagent.py — a small dedicated agent whose
ONLY job is grounding a location-aware suggestion, wrapped as an
AgentTool for AetherPresenceAgent to call.
"""

from google.adk.agents import Agent
from google.adk.tools import google_maps_grounding
from google.adk.tools.agent_tool import AgentTool
from config import MODEL_NAME

INSTRUCTION = """You are a focused location helper. Given a user's
general area/city and a short description of what kind of nearby break
or activity might help them (e.g. "a quiet walk" or "a nearby cafe"),
use google_maps_grounding to find ONE real, plausible nearby option.

Return a short plain-text answer naming the real place and a one-line
reason it fits. Never invent a place name — only report what the tool
actually grounds."""


def build_location_subagent() -> Agent:
    return Agent(
        name="doneho_location_subagent",
        model=MODEL_NAME,
        description="Grounds one real nearby suggestion using the user's general location.",
        instruction=INSTRUCTION,
        tools=[google_maps_grounding],
    )


def build_location_agent_tool() -> AgentTool:
    return AgentTool(agent=build_location_subagent())
