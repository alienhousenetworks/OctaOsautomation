import json
from typing import Dict, Any, List

def convert_trajectory_to_sft(trajectory_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms logged execution trajectory into HuggingFace SFT Chat format:
    {
       "messages": [
           {"role": "system", "content": "..."},
           {"role": "user", "content": "..."},
           {"role": "assistant", "content": "<thought>...</thought>\n```json\n...\n```"}
       ]
    }
    """
    system_instructions = trajectory_record.get(
        "system_instructions", 
        "You are an enterprise AI Manager Orchestrator. Plan, reason step-by-step, and execute tools."
    )
    
    messages = [
        {"role": "system", "content": system_instructions}
    ]
    
    steps = trajectory_record.get("steps", [])
    initial_user_prompt = trajectory_record.get("initial_user_prompt", "")
    
    if initial_user_prompt:
        messages.append({"role": "user", "content": initial_user_prompt})
        
    for step in steps:
        assistant_content = ""
        
        # Inject reasoning thought process if present
        thought = step.get("thought_process")
        if thought:
            assistant_content += f"<thought>\n{thought}\n</thought>\n"
            
        tool_calls = step.get("tool_calls")
        final_text = step.get("final_text_response")
        
        if tool_calls:
            assistant_content += f"```json\n{json.dumps(tool_calls, indent=2)}\n```"
        elif final_text:
            assistant_content += final_text
            
        if assistant_content.strip():
            messages.append({"role": "assistant", "content": assistant_content.strip()})
            
        # If step had tool output, present it back as tool user feedback
        tool_outputs = step.get("tool_outputs")
        if tool_outputs:
            messages.append({
                "role": "user", 
                "content": f"Tool Execution Output:\n```json\n{json.dumps(tool_outputs, indent=2)}\n```"
            })
            
    return {"messages": messages}


def batch_export_sft_dataset(trajectories: List[Dict[str, Any]], output_filepath: str):
    """Exports dataset to jsonl file for Unsloth / HuggingFace training."""
    with open(output_filepath, "w", encoding="utf-8") as f:
        for traj in trajectories:
            sft_record = convert_trajectory_to_sft(traj)
            f.write(json.dumps(sft_record) + "\n")
