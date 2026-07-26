from typing import Dict, Any

class ModelRouter:
    """
    Dynamic Model Router: Selects optimal inference provider based on task complexity,
    routing 80% of routine steps to fine-tuned local SLMs (Qwen/Llama) and falling back
    to Frontier Models (Claude/GPT-4o) only for high-risk or novel creative tasks.
    """
    
    def __init__(
        self,
        local_slm_7b_url: str = "http://localhost:8000/v1",
        local_slm_14b_url: str = "http://localhost:8001/v1",
        frontier_model: str = "gpt-4o"
    ):
        self.local_slm_7b_url = local_slm_7b_url
        self.local_slm_14b_url = local_slm_14b_url
        self.frontier_model = frontier_model

    def select_route(self, task_description: str, roi_priority: int, risk_level: str = "NORMAL") -> Dict[str, Any]:
        """
        Determines model assignment and endpoint URL.
        """
        # Critical risk or novelty -> Frontier fallback
        if risk_level == "CRITICAL" or "security audit" in task_description.lower():
            return {
                "provider": "frontier",
                "model_name": self.frontier_model,
                "url": "https://api.openai.com/v1/chat/completions",
                "reason": "High security/risk task requires frontier reasoning"
            }
            
        # Medium complexity / priority 1-2 -> 14B Fine-Tuned SLM
        elif roi_priority <= 2 or len(task_description) > 200:
            return {
                "provider": "slm_14b",
                "model_name": "qwen-orchestrator-14b",
                "url": f"{self.local_slm_14b_url}/chat/completions",
                "reason": "Medium complexity routed to fine-tuned 14B SLM"
            }
            
        # Standard routine task -> 7B Fine-Tuned SLM (Maximum Token ROI)
        else:
            return {
                "provider": "slm_7b",
                "model_name": "qwen-orchestrator-7b",
                "url": f"{self.local_slm_7b_url}/chat/completions",
                "reason": "Routine task routed to fine-tuned 7B local SLM"
            }
