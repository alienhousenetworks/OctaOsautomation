from typing import Dict, Any

class QualityGate:
    """Reflective Quality Gate that verifies sub-agent outputs before accepting results."""
    
    @staticmethod
    def inspect_result(task_id: str, output_content: str) -> Dict[str, Any]:
        if not output_content or len(output_content.strip()) < 15:
            return {
                "passed": False,
                "reason": f"Output for {task_id} is too short or empty."
            }
            
        error_keywords = ["Exception:", "Traceback (most recent call last):", "HTTP 500", "Fatal error"]
        for kw in error_keywords:
            if kw in output_content:
                return {
                    "passed": False,
                    "reason": f"Execution output contained error signature: '{kw}'"
                }
                
        return {
            "passed": True,
            "reason": "Output passed format and validity verification."
        }

    @staticmethod
    def generate_reflection_prompt(failed_task_id: str, task_desc: str, error_reason: str) -> str:
        return f"""
<reflection>
Sub-task '{failed_task_id}' ({task_desc}) failed quality inspection:
Reason: {error_reason}

Analyze why this failed, correct tool inputs, and re-execute.
</reflection>
"""
