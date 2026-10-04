import re
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.base import APICredential
from app.core.security import encrypt_api_key, decrypt_api_key

logger = logging.getLogger(__name__)

class DecryptionError(Exception):
    """Custom exception raised when credential decryption fails."""
    pass

class EncryptionService:
    @staticmethod
    def encrypt(key: str) -> str:
        if not key:
            return ""
        return encrypt_api_key(key)

    @staticmethod
    def decrypt(encrypted_key: str) -> str:
        if not encrypted_key:
            return ""
        try:
            decrypted = decrypt_api_key(encrypted_key)
            # Check if decrypt_api_key actually returned a decrypted key or threw an exception
            # We will handle exceptions from app.core.security inside its updated implementation.
            return decrypted
        except Exception as e:
            logger.error(f"Failed to decrypt secure credential: {e}")
            raise DecryptionError("Decryption failed. Invalid key or corrupted data.") from e

class SecretMaskingService:
    @staticmethod
    def mask_secret(secret: str) -> str:
        if not secret:
            return ""
        
        # Strip whitespaces
        secret = secret.strip()
        
        if len(secret) <= 8:
            return "*" * len(secret)
            
        # Detect common prefix patterns
        prefixes = ["sk-proj-", "sk-ant-", "sk-", "key-", "bearer ", "Bearer "]
        matched_prefix = ""
        for p in prefixes:
            if secret.lower().startswith(p.lower()):
                matched_prefix = secret[:len(p)]
                secret = secret[len(p):]
                break
                
        if len(secret) <= 4:
            return matched_prefix + "*" * len(secret)
            
        masked_part = "*" * (len(secret) - 4)
        visible_part = secret[-4:]
        return f"{matched_prefix}{masked_part}{visible_part}"

class SecretValidationService:
    @staticmethod
    def validate_api_key(provider: str, api_key: str) -> bool:
        if not api_key:
            return False
        provider_lower = provider.lower()
        if provider_lower == "openai":
            # sk-proj-... or sk-...
            return bool(re.match(r"^sk-(proj-)?[a-zA-Z0-9_-]{20,}$", api_key))
        elif provider_lower == "anthropic":
            # sk-ant-...
            return bool(re.match(r"^sk-ant-[a-zA-Z0-9_-]{20,}$", api_key))
        elif provider_lower == "openrouter":
            return bool(re.match(r"^sk-or-[a-zA-Z0-9_-]{10,}$", api_key)) or len(api_key) >= 15
        elif provider_lower in ("together", "togetherapi"):
            return len(api_key) >= 15
        elif provider_lower == "groq":
            return bool(re.match(r"^gsk_[a-zA-Z0-9_-]{15,}$", api_key)) or len(api_key) >= 15
        elif provider_lower in ("grok", "xai"):
            return bool(re.match(r"^xai-[a-zA-Z0-9_-]{15,}$", api_key)) or len(api_key) >= 15
        elif provider_lower == "gemini":
            # API keys are typically ~40 chars long
            return len(api_key) >= 20
        elif provider_lower.startswith("smtp"):
            # smtp://username:password@host:port
            return api_key.startswith("smtp://") or "@" in api_key
        elif provider_lower == "ai_mode":
            return api_key.lower() in ("inbuilt", "byok")
        # Default minimum validation length
        return len(api_key) >= 8

class SecretRotationSupport:
    @staticmethod
    def rotate_credentials(
        db: Session,
        tenant_id: str,
        provider: str,
        new_key: str,
        settings: Optional[Dict[str, Any]] = None
    ) -> APICredential:
        if not SecretValidationService.validate_api_key(provider, new_key):
            raise ValueError(f"Invalid key format for provider: {provider}")
            
        encrypted_val = EncryptionService.encrypt(new_key)
        
        cred = db.query(APICredential).filter(
            APICredential.tenant_id == tenant_id,
            APICredential.provider == provider.lower()
        ).first()
        
        if cred:
            cred.encrypted_key = encrypted_val
            if settings is not None:
                cred.settings = {**(cred.settings or {}), **settings}
        else:
            cred = APICredential(
                tenant_id=tenant_id,
                provider=provider.lower(),
                encrypted_key=encrypted_val,
                settings=settings or {}
            )
            db.add(cred)
            
        db.commit()
        db.refresh(cred)
        return cred
