"""
Shared helper for invoking ADK agents synchronously and returning parsed,
structured output. Every DoneHo agent (Clarification, Blueprint, Nudge,
Recalibration) goes through this so the Runner/session boilerplate lives
in exactly one place.
"""

import asyncio
import uuid
from typing import Type, TypeVar

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

T = TypeVar("T")

APP_NAME = "doneho"
_session_service = InMemorySessionService()


def run_agent_sync(agent: Agent, prompt: str, output_model: Type[T], user_id: str = "doneho_user") -> T:
    """
    Runs a single-turn ADK agent call synchronously and parses the final
    response text into `output_model` (a Pydantic model matching the
    agent's output_schema). Creates a fresh session per call — DoneHo
    agents are stateless per-invocation; Shared Execution State is the
    real persistence layer, not ADK session memory.
    """
    return asyncio.run(_run_agent_async(agent, prompt, output_model, user_id))


async def _run_agent_async(agent: Agent, prompt: str, output_model: Type[T], user_id: str) -> T:
    session_id = str(uuid.uuid4())
    await _session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)

    runner = Runner(agent=agent, app_name=APP_NAME, session_service=_session_service)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    final_text = ""
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    return output_model.model_validate_json(final_text)
