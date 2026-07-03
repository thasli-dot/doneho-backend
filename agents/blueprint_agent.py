"""
BlueprintAgent (Build Brief, Section 3.4, 5, 6).

The core planner. Runs DeterministicEngine FIRST (via the orchestrator,
not this file — see Section 3.1/3.4: "Runs Deterministic Engine first,
then reasons over goals/tasks/context"), then decomposes every goal's
tasks into specific, concrete weekly milestones sized against the
per-goal hour allocation the DeterministicEngine already computed.

Hard rules enforced via instruction:
- Milestones must be specific and concrete, never generic phase labels
  ("Foundation / Practice / Revision / Evaluation" is explicitly banned).
- Every goal and every task gets at least one real milestone — never
  silently dropped, even Low-focus ones.
- Output is short, checkable points, not descriptive sentences.
"""

from google.adk.agents import Agent
from models.schemas import Goal, BlueprintAgentOutput
from core.agent_runner import run_agent_sync
from config import MODEL_NAME

INSTRUCTION = """You are DoneHo's Blueprint Agent — the core weekly planner.

You will be given, for each goal: its category, focus level (High/Medium/Low),
its allocated hours for the week (already computed deterministically — do
not recalculate or second-guess this number), and its list of tasks
(each possibly with a clarification note giving extra context).

For EVERY task under EVERY goal, generate one or more specific, concrete
weekly milestones that together fit within that goal's allocated hours.

Hard rules:
- NEVER use generic phase labels like "Foundation", "Practice", "Revision",
  "Evaluation", "Getting Started", "Deep Dive" as milestone titles. Every
  milestone must name a specific, concrete action.
  Correct example: goal "Learn SQL" -> milestones "Set up local SQL
  environment", "Practice basic SELECT/WHERE queries" — not generic phases.
- Every single task must receive AT LEAST ONE milestone. Do not silently
  drop a task, even if its goal is Low focus.
- Milestone titles must be short, checkable points (something a user could
  tick off), not long descriptive sentences.
- Assign each milestone a realistic expected_hours that is honest about
  what the task needs, and that collectively roughly sums to the goal's
  allocated hours across all its milestones.
- Fill goal_id, goal_title, task_id, task_title on every milestone exactly
  as given in the input — do not invent or alter IDs.

Return ONLY the structured output. No extra commentary."""


def build_blueprint_agent() -> Agent:
    return Agent(
        name="blueprint_agent",
        model=MODEL_NAME,
        description="Decomposes goals/tasks into concrete weekly milestones.",
        instruction=INSTRUCTION,
        output_schema=BlueprintAgentOutput,
    )


def run_blueprint(goals: list[Goal], hours_by_goal: dict[str, float]) -> BlueprintAgentOutput:
    lines = []
    for g in goals:
        allocated = hours_by_goal.get(g.id, 0)
        lines.append(f"\nGoal: {g.category.value} (id={g.id}, focus={g.focus_level}, allocated_hours={allocated})")
        for t in g.tasks:
            note = f" [clarified: {t.clarification_note}]" if t.clarification_note else ""
            lines.append(f"  - Task id={t.id}: \"{t.title}\"{note}")

    prompt = "Goals and tasks for this week's Blueprint:\n" + "\n".join(lines)

    agent = build_blueprint_agent()
    return run_agent_sync(agent, prompt, BlueprintAgentOutput)
