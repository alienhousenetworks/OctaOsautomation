import json
import httpx
from typing import Dict, Any, List

JUDGE_PROMPT_TEMPLATE = """
You are an expert AI Dataset Auditor and Quality Judge.
Analyze the following LLM trajectory to determine if it is suitable for training a enterprise-grade Small Language Model (SLM) Orchestrator.

User Initial Prompt: {user_prompt}

Execution Trajectory Steps:
{trajectory_steps}

Evaluate the trajectory on a 1.0 to 5.0 scale across these dimensions:
1. Goal Accomplishment & Accuracy
2. Tool Argument Precision & Efficiency
3. Business Context & ROI Realization

Return ONLY valid JSON matching this schema:
{{
  "score": 4.8,
  "reasoning": "Clear plan, highly efficient tool calls, accurate response.",
  "is_usable_for_sft": true,
  "suggested_category": "task_orchestration"
}}
"""

class TrajectoryEvaluator:
    """Uses LLM-as-a-Judge to grade trajectories and filter dataset quality."""
    
    def __init__(self, judge_model: str = "gpt-4o", api_key: str = None):
        self.judge_model = judge_model
        self.api_key = api_key

    async def evaluate_trajectory(self, user_prompt: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        steps_str = json.dumps(steps, indent=2)
        formatted_prompt = JUDGE_PROMPT_TEMPLATE.format(
            user_prompt=user_prompt,
            trajectory_steps=steps_str
        )
        
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.judge_model,
            "messages": [{"role": "user", "content": formatted_prompt}],
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient() as client:
            res = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=30.0)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            else:
                return {
                    "score": 1.0,
                    "reasoning": f"Judge API error: {res.status_code}",
                    "is_usable_for_sft": False,
                    "suggested_category": "error"
                }
