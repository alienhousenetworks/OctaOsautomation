import os
import json
try:
    import yaml
except ImportError:
    yaml = None
from typing import Dict, List, Any, Optional

class SkillMetadata:
    def __init__(self, name: str, description: str, category: str, triggers: List[str]):
        self.name = name
        self.description = description
        self.category = category
        self.triggers = triggers

class ProgressiveSkillSynthesizer:
    """
    Progressive Token Disclosure & Autonomous Skill Synthesizer.
    
    Prevents token bloat by exposing skills in 3 progressive levels:
    - Level 1 (~20 tokens): Skill name & concise summary
    - Level 2 (~200 tokens): Input parameters & schema definitions
    - Level 3 (Full body): Procedural step-by-step tool execution body
    """
    
    def __init__(self, base_skills_dir: Optional[str] = None):
        self.base_skills_dir = base_skills_dir or os.path.expanduser("~/.octaos/skills")
        os.makedirs(self.base_skills_dir, exist_ok=True)

    def distill_execution_trace(self, skill_name: str, description: str, 
                                category: str, triggers: List[str],
                                execution_steps: List[Dict[str, Any]]) -> str:
        """
        Distills a successful multi-step agent execution trace into a standardized SKILL.md document.
        """
        skill_dir = os.path.join(self.base_skills_dir, skill_name.lower().replace(" ", "_"))
        os.makedirs(skill_dir, exist_ok=True)
        
        skill_path = os.path.join(skill_dir, "SKILL.md")
        
        frontmatter = {
            "name": skill_name,
            "description": description,
            "category": category,
            "triggers": triggers,
            "version": "1.0.0"
        }
        
        frontmatter_str = yaml.dump(frontmatter) if yaml else json.dumps(frontmatter, indent=2)
        content = f"---\n{frontmatter_str}---\n\n"
        content += f"# Skill: {skill_name}\n\n"
        content += f"## Overview\n{description}\n\n"
        content += "## Procedural Execution Steps\n"
        
        for idx, step in enumerate(execution_steps, 1):
            content += f"### Step {idx}: {step.get('action', 'Execute Action')}\n"
            content += f"- **Tool**: `{step.get('tool', 'system')}`\n"
            content += f"- **Parameters**: `{json.dumps(step.get('params', {}))}`\n"
            if step.get('notes'):
                content += f"- **Notes**: {step.get('notes')}\n"
            content += "\n"
            
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return skill_path

    def get_skill_disclosure(self, skill_name: str, level: int = 1) -> str:
        """
        Returns skill content according to progressive token disclosure level (1, 2, or 3).
        """
        skill_dir = os.path.join(self.base_skills_dir, skill_name.lower().replace(" ", "_"))
        skill_path = os.path.join(skill_dir, "SKILL.md")
        
        if not os.path.exists(skill_path):
            return f"Skill '{skill_name}' not found."
            
        with open(skill_path, "r", encoding="utf-8") as f:
            full_text = f.read()
            
        parts = full_text.split("---")
        metadata = {}
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) if yaml else json.loads(parts[1])
            except Exception:
                metadata = {}
            
        if level == 1:
            # Level 1 (~20 tokens): Name + description
            return f"Skill `{metadata.get('name', skill_name)}`: {metadata.get('description', '')}"
        elif level == 2:
            # Level 2 (~200 tokens): Triggers & schema overview
            return (
                f"Skill: {metadata.get('name', skill_name)}\n"
                f"Description: {metadata.get('description', '')}\n"
                f"Category: {metadata.get('category', 'general')}\n"
                f"Triggers: {', '.join(metadata.get('triggers', []))}"
            )
        else:
            # Level 3: Full execution body
            return full_text

skill_synthesizer = ProgressiveSkillSynthesizer()
