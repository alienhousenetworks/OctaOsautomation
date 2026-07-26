import time
import uuid
import httpx
from typing import Dict, Any, List
from app.octa_orchestrator.orchestrator.decomposer import DAGDecomposer, ExecutionPlanDAG
from app.octa_orchestrator.orchestrator.router import ModelRouter
from app.octa_orchestrator.orchestrator.quality_gate import QualityGate

class AIManagerOrchestrator:
    """
    The Executive AI Manager: Coordinates multi-agent workflows like an experienced manager,
    evaluating ROI, generating DAG task graphs, routing tasks to SLMs, and reflecting on results.
    """
    
    def __init__(self, api_key: str = None):
        self.decomposer = DAGDecomposer(api_key=api_key)
        self.router = ModelRouter()
        self.quality_gate = QualityGate()
        self.api_key = api_key

    async def execute_goal(self, user_goal: str, risk_level: str = "NORMAL") -> Dict[str, Any]:
        start_time = time.time()
        trajectory_id = str(uuid.uuid4())
        
        print(f"[AI Manager] Initiating goal execution: '{user_goal}' | ID: {trajectory_id}")
        
        # 1. Generate DAG Plan
        dag_plan: ExecutionPlanDAG = await self.decomposer.decompose_goal(user_goal)
        print(f"[AI Manager] Generated DAG with {len(dag_plan.tasks)} sub-tasks | Est. ROI: {dag_plan.estimated_total_roi}")
        
        completed_results: Dict[str, Any] = {}
        execution_logs: List[Dict[str, Any]] = []
        
        # 2. Iterate through DAG Sub-tasks
        for task in dag_plan.tasks:
            # Check route selection
            route = self.router.select_route(task.description, task.roi_priority, risk_level)
            print(f"[AI Manager] Executing {task.task_id} via route: {route['provider']} ({route['model_name']})")
            
            # Construct sub-task execution payload
            prompt = f"Goal Context: {user_goal}\nSub-task: {task.description}\nDependencies Output: {completed_results}"
            
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            payload = {
                "model": route["model_name"] if route["provider"] == "frontier" else "gpt-4o",
                "messages": [
                    {"role": "system", "content": f"You are a specialized worker agent: {task.assigned_agent}."},
                    {"role": "user", "content": prompt}
                ]
            }
            
            # Execute sub-task call
            async with httpx.AsyncClient() as client:
                res = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=40.0)
                if res.status_code == 200:
                    output_text = res.json()["choices"][0]["message"]["content"]
                else:
                    output_text = f"Execution failed with status: {res.status_code}"

            # Quality Reflection Gate Check
            verification = self.quality_gate.inspect_result(task.task_id, output_text)
            if not verification["passed"]:
                print(f"[AI Manager Quality Warning] {task.task_id} failed inspection: {verification['reason']}")
                # Self-correction attempt
                correction_prompt = self.quality_gate.generate_reflection_prompt(task.task_id, task.description, verification["reason"])
                payload["messages"].append({"role": "assistant", "content": output_text})
                payload["messages"].append({"role": "user", "content": correction_prompt})
                
                async with httpx.AsyncClient() as client:
                    res_corr = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=40.0)
                    if res_corr.status_code == 200:
                        output_text = res_corr.json()["choices"][0]["message"]["content"]

            completed_results[task.task_id] = output_text
            execution_logs.append({
                "task_id": task.task_id,
                "description": task.description,
                "route": route,
                "output": output_text
            })

        total_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "trajectory_id": trajectory_id,
            "user_goal": user_goal,
            "estimated_roi": dag_plan.estimated_total_roi,
            "sub_tasks_executed": len(dag_plan.tasks),
            "results": completed_results,
            "logs": execution_logs,
            "execution_time_ms": total_time_ms
        }
