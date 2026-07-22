import os
import re
from typing import Dict, Any

class UserProfileEngine:
    """
    Dynamic User & Environment Profiling Engine for OctaOS Local Node Daemon (~/.octaos/USER.md).
    Learns coding stack, framework preferences, and operational rules over time.
    """
    def __init__(self, profile_path: str = None):
        self.profile_path = profile_path or os.path.expanduser("~/.octaos/USER.md")
        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
        self._ensure_profile_exists()

    def _ensure_profile_exists(self):
        if not os.path.exists(self.profile_path):
            initial_content = (
                "# OctaOS User Profile & System Context\n\n"
                "## Technical Environment\n"
                "- OS: macOS / Unix\n"
                "- Primary Languages: Python, JavaScript/TypeScript, SQL\n"
                "- Frameworks: FastAPI, Next.js, PostgreSQL\n\n"
                "## Developer Preferences\n"
                "- Coding Style: Clean, modular, type-annotated\n"
                "- Test Framework: pytest\n"
                "- Database Preference: PostgreSQL (Cloud), SQLite (Local)\n\n"
                "## Learned Workflows & Rules\n"
                "- Always inspect full log tracebacks before diagnosing errors.\n"
                "- Validate commands before execution.\n"
            )
            with open(self.profile_path, "w", encoding="utf-8") as f:
                f.write(initial_content)

    def read_profile(self) -> str:
        with open(self.profile_path, "r", encoding="utf-8") as f:
            return f.read()

    def update_preference(self, key: str, value: str):
        content = self.read_profile()
        new_entry = f"- {key}: {value}\n"
        if key in content:
            content = re.sub(rf"- {key}:.*", new_entry.strip(), content)
        else:
            content += f"\n{new_entry}"
        with open(self.profile_path, "w", encoding="utf-8") as f:
            f.write(content)

user_profile = UserProfileEngine()
