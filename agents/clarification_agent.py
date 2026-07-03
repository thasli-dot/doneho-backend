"""
ClarificationAgent (Build Brief, Section 3.4, 6, 8 step 2).

Scans user-entered tasks, flags GENUINELY ambiguous ones only, generates
one targeted follow-up question per flagged task. Must NOT ask a fixed
question for every task — self-evident tasks ("Workout", "Meditation")
get no question at all.
"""

from google.adk.agents import Agent
from models.schemas import Task, ClarificationAgentOutput
from core.agent_runner import run_agent_sync
from config import MODEL_NAME

INSTRUCTION = """You are DoneHo's Clarification Agent.

You will be given a list of user-entered tasks (each with an id and title).
For EACH task, decide whether it is genuinely ambiguous — meaning a
reasonable planner could not proceed without more information because the
scope, intensity, level, or type is unclear.

Rules:
- Do NOT flag self-evident tasks. "Workout", "Meditation", "Healthy recipes",
  "Read a book", "Cook dinner" are NOT ambiguous — they are clear enough to
  plan around as-is.
- DO flag genuinely vague tasks, e.g. "Learn Python" (from scratch, or
  brushing up?), "Get fit" (what does that mean specifically?), "Work on
  project" (which project, what kind of work?).
- For every flagged task, write ONE short, specific, conversational
  question tailored to THAT task's actual domain and phrasing. Never reuse
  a generic fallback question across different tasks. A vague fitness task
  gets a fitness-relevant question; a vague study task gets a study-relevant
  question; and so on.
- Keep every question short, crisp, everyday English — one sentence, no
  preamble.
- If a task is not ambiguous, set is_ambiguous to false and leave question
  null. Do not skip any task from the output list — every input task must
  appear exactly once in flags.

Return ONLY the structured output. No extra commentary."""


def build_clarification_agent() -> Agent:
    return Agent(
        name="clarification_agent",
        model=MODEL_NAME,
        description="Flags genuinely ambiguous tasks and drafts targeted follow-up questions.",
        instruction=INSTRUCTION,
        output_schema=ClarificationAgentOutput,
    )


def run_clarification(tasks: list[Task]) -> ClarificationAgentOutput:
    if not tasks:
        return ClarificationAgentOutput(flags=[])

    task_lines = "\n".join(f"- id={t.id}: \"{t.title}\"" for t in tasks)
    prompt = f"Tasks to review:\n{task_lines}"

    agent = build_clarification_agent()
    return run_agent_sync(agent, prompt, ClarificationAgentOutput)
