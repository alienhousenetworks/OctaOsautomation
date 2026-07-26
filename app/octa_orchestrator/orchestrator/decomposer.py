import json
import httpx
from pydantic import BaseModel
from typing import List, Optional

class SubTask(BaseModel):
    task_id: str
    description: str
    assigned_agent: str  # e.g., "data_collector", "market_analyst", "code_executor"
    dependencies: List[str]
    roi_priority: int  # 1 (Critical) to 5 (Low)

class ExecutionPlanDAG(BaseModel):
    goal: str
    tasks: List[SubTask]
    estimated_total_roi: str

DECOMPOSER_PROMPT = """
You are the AI Executive Manager. Break down the user's high-level request into a Directed Acyclic Graph (DAG) of actionable sub-tasks.
Each task must be assigned to an appropriate specialized worker sub-agent.
Prioritize sub-tasks by business ROI and list explicit dependencies.

Return ONLY valid JSON matching this schema:
{{
  "goal": "Original user goal",
  "tasks": [
    {{
      "task_id": "task_1",
      "description": "Extract market trend metrics",
      "assigned_agent": "market_analyst",
      "dependencies": [],
      "roi_priority": 1
    }}
  ],
  "estimated_total_roi": "High ROI - expected 5x efficiency improvement"
}}
"""

class DAGDecomposer:
    """Decomposes vague user requests into structured, executable DAG graphs."""
    
    def __init__(self, slm_url: str = None, api_key: str = None):
        self.slm_url = slm_url or "https://api.openai.com/v1/chat/completions"
        self.api_key = api_key

    async def decompose_goal(self, user_goal: str, model_name: str = "gpt-4o") -> ExecutionPlanDAG:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": DECOMPOSER_PROMPT},
                {"role": "user", "content": f"User Goal: {user_goal}"}
            ],
            "response_format": {"type": "json_object"}
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

        async with httpx.AsyncClient() as client:
            res = await client.post(self.slm_url, json=payload, headers=headers, timeout=40.0)
            if res.status_code == 200:
                data = res.json()["choices"][0]["message"]["content"]
                parsed = json.loads(data)
                return ExecutionPlanDAG(**parsed)
            else:
                # Fallback simple DAG
                return ExecutionPlanDAG(
                    goal=user_goal,
                    tasks=[
                        SubTask(
                            task_id="task_1",
                            description=user_goal,
                            assigned_agent="general_worker",
                            dependencies=[],
                            roi_priority=1
                        )
                    ],
                    estimated_total_roi="Standard execution"
                )
