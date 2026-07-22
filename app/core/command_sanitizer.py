import re
from enum import Enum
from typing import Tuple

class ExecutionMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    SEMI_AUTONOMOUS = "SEMI_AUTONOMOUS"
    FULLY_AUTONOMOUS = "FULLY_AUTONOMOUS"

class CommandSanitizer:
    """
    Zero-Trust Security Guardrail to inspect terminal commands and tool scripts
    before execution on local node daemons or remote enterprise workers.
    """
    
    # Destructive commands that are strictly prohibited regardless of mode
    BLOCKED_PATTERNS = [
        r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+(/|~|\*|/\*)",
        r"mkfs",
        r"dd\s+if=",
        r">\s*/dev/sd[a-z]",
        r":\(\)\{\s*:\|:&\s*\};:", # Fork bomb
        r"chmod\s+(-R\s+)?777\s+/",
        r"cat\s+/etc/shadow",
        r"cat\s+/etc/sudoers",
        r"curl\s+.*\|\s*sh",
        r"wget\s+.*\|\s*bash",
        r"eval\(.*base64_decode"
    ]
    
    # Write or modifying patterns that require user approval in SEMI_AUTONOMOUS mode
    MODIFYING_PATTERNS = [
        r"git\s+push",
        r"docker\s+run",
        r"kubectl\s+apply",
        r"npm\s+publish",
        r"pip\s+install",
        r"sudo\s+",
        r"rm\s+",
        r"mv\s+",
        r">\s*",
        r">>\s*"
    ]

    def inspect_command(self, command: str, mode: ExecutionMode = ExecutionMode.SEMI_AUTONOMOUS) -> Tuple[bool, str, bool]:
        """
        Inspects a shell command.
        Returns:
            (is_allowed: bool, reason: str, requires_user_approval: bool)
        """
        cleaned_cmd = command.strip()
        
        # 1. Check for hard blocked malicious/destructive patterns
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, cleaned_cmd, re.IGNORECASE):
                return False, f"Command blocked due to high-risk pattern match: {pattern}", False

        # 2. Check mode restrictions
        if mode == ExecutionMode.READ_ONLY:
            # If mode is READ_ONLY, reject any command matching modifying patterns
            for pattern in self.MODIFYING_PATTERNS:
                if re.search(pattern, cleaned_cmd, re.IGNORECASE):
                    return False, f"Command rejected in READ_ONLY mode: modifying operation detected ({pattern})", False
            return True, "Command allowed in READ_ONLY mode", False

        elif mode == ExecutionMode.SEMI_AUTONOMOUS:
            # Require explicit approval for write/destructive/system ops
            for pattern in self.MODIFYING_PATTERNS:
                if re.search(pattern, cleaned_cmd, re.IGNORECASE):
                    return True, "Modifying command requires user confirmation", True
            return True, "Read-only command auto-approved", False

        elif mode == ExecutionMode.FULLY_AUTONOMOUS:
            return True, "Command approved for autonomous execution", False

        return False, "Unknown execution mode", False

sanitizer = CommandSanitizer()
