import re
from typing import Any, Dict, List, Union

class DataSanitizer:
    """PII & Secret Redaction Engine to clean interaction logs before storage/training."""
    
    def __init__(self):
        self.patterns = {
            "api_key": r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{20,}|sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36}|key-[a-zA-Z0-9]{32,})",
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
            "phone": r"\b\d{3}[-.\s]??\d{3}[-.\s]??\d{4}\b",
            "jwt": r"eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"
        }

    def sanitize_text(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return text or ""
        sanitized = text
        for key, pattern in self.patterns.items():
            sanitized = re.sub(pattern, f"[REDACTED_{key.upper()}]", sanitized)
        return sanitized

    def sanitize_payload(self, payload: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
        """Recursively sanitizes dictionaries, lists, and raw string payloads."""
        if isinstance(payload, str):
            return self.sanitize_text(payload)
        elif isinstance(payload, dict):
            return {k: self.sanitize_payload(v) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [self.sanitize_payload(item) for item in payload]
        return payload
