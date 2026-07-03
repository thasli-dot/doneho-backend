"""
Search sub-agent (Build Brief, Section 7 Item 5 / Section 12.1 / Roadmap
Entry 4). ADK's built-in `google_search` tool cannot be combined with
`output_schema` on the same agent, so this small dedicated agent's ONLY
job is searching. NudgeAgent calls it as an AgentTool rather than using
google_search directly.
"""

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from config import MODEL_NAME

INSTRUCTION = """You are a focused research helper. Given a short query
describing something a user might want to buy, watch, or read to save
time on a task, use google_search to find ONE real, currently-live,
relevant result (a product listing, tutorial video, article, or service).

Return a short plain-text answer: the result's title and its real URL,
exactly as returned by the search tool. Never invent or guess a URL —
only report a URL that actually came back from google_search."""


def build_search_subagent() -> Agent:
    return Agent(
        name="doneho_search_subagent",
        model=MODEL_NAME,
        description="Searches the live web for one real, relevant link to support a suggestion.",
        instruction=INSTRUCTION,
        tools=[google_search],
    )


def build_search_agent_tool() -> AgentTool:
    return AgentTool(agent=build_search_subagent())
