import json
from typing import Dict, Any, List

def format_dpo_pair(
    user_prompt: str,
    chosen_trajectory: Dict[str, Any],
    rejected_trajectory: Dict[str, Any],
    system_instructions: str = "You are an AI Manager Orchestrator."
) -> Dict[str, Any]:
    """
    Formats paired comparison records for Direct Preference Optimization (DPO):
    {
       "prompt": "...",
       "chosen": [{"role": "assistant", "content": "..."}],
       "rejected": [{"role": "assistant", "content": "..."}]
    }
    """
    chosen_steps = chosen_trajectory.get("steps", [])
    rejected_steps = rejected_trajectory.get("steps", [])
    
    chosen_text = "\n".join([s.get("final_text_response", "") for s in chosen_steps])
    rejected_text = "\n".join([s.get("final_text_response", "") for s in rejected_steps])
    
    return {
        "system": system_instructions,
        "prompt": user_prompt,
        "chosen": chosen_text,
        "rejected": rejected_text
    }


def batch_export_dpo_dataset(dpo_pairs: List[Dict[str, Any]], output_filepath: str):
    """Exports DPO pairs to JSONL file for alignment training."""
    with open(output_filepath, "w", encoding="utf-8") as f:
        for pair in dpo_pairs:
            f.write(json.dumps(pair) + "\n")
