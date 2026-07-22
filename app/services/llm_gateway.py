from typing import Any, Dict, List, Optional
import httpx
import base64
from app.core.config import settings
from app.models.base import ProviderUsage
from sqlalchemy.orm import Session
import time
from app.services.media.storage import ensure_public_url

class LLMGateway:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    async def _track_usage(self, provider: str, model: str, input_tokens: int, output_tokens: int):
        # Rough cost calculation based on PRD v4.0
        # Haiku: $0.25 / 1M input, $1.25 / 1M output
        # Sonnet: $3 / 1M input, $15 / 1M output
        cost = 0.0
        if "haiku" in model.lower():
            cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)
        elif "sonnet" in model.lower():
            cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
        elif "gpt-4o" in model.lower():
            cost = (input_tokens * 5.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000) # Placeholder for GPT-4o
        
        usage = ProviderUsage(
            tenant_id=self.tenant_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost
        )
        self.db.add(usage)
        self.db.commit()

    def _get_api_key(self, provider: str) -> str:
        from app.services.credentials import get_decrypted_credential

        key, _ = get_decrypted_credential(self.db, self.tenant_id, provider)
        if key:
            return key
        
        # Fall back to environment variables
        if provider == "anthropic":
            return settings.SHARED_CLAUDE_KEY or settings.ANTHROPIC_API_KEY
        elif provider == "openai":
            return settings.OPENAI_API_KEY
        elif provider == "gemini":
            import os
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        elif provider == "grok":
            import os
            return os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or ""
        elif provider in ["kimi", "moonshot"]:
            import os
            return os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or ""
        return ""
    async def complete(self, prompt: str, model: str = None, provider: str = "anthropic", system_prompt: str = None, **kwargs) -> str:
        from app.services.ai_gateway import ai_gateway
        
        # 1. Infer task parameters for optimization routing
        inferred_task_type = "general"
        combined_text = (prompt + " " + (system_prompt or "")).lower()
        if any(w in combined_text for w in ["marketing", "campaign", "instagram", "facebook", "linkedin", "social media", "post"]):
            inferred_task_type = "marketing"
        elif any(w in combined_text for w in ["sales", "lead", "outreach", "prospect", "apollo", "hunter", "pitch"]):
            inferred_task_type = "sales"
        elif any(w in combined_text for w in ["support", "ticket", "whatsapp", "customer", "reply", "faq"]):
            inferred_task_type = "support"
        elif any(w in combined_text for w in ["hr", "candidate", "interview", "recruiter", "hiring"]):
            inferred_task_type = "hr"
        elif any(w in combined_text for w in ["finance", "invoice", "billing", "budget"]):
            inferred_task_type = "finance"

        # 1b. Automatically fetch and inject relevant knowledge base documents to system prompt
        from app.models.agents import KnowledgeDocument
        dept_map = {
            "marketing": "Marketing",
            "sales": "Sales",
            "support": "Support",
            "hr": "HR",
            "finance": "Finance",
            "general": None
        }
        dept_name = dept_map.get(inferred_task_type)
        
        try:
            query = self.db.query(KnowledgeDocument).filter(
                KnowledgeDocument.tenant_id == self.tenant_id
            )
            if dept_name:
                query = query.filter(KnowledgeDocument.department.in_([dept_name, "General"]))
            
            docs = query.all()
            if docs:
                knowledge_str = (
                    "Company Guidelines & Knowledge Base:\n"
                    "CRITICAL INSTRUCTION: You must strictly adhere to the company guidelines, brand rules, "
                    "contact details (e.g. email, phone), and websites listed below. Incorporate them "
                    "into your generated output (social posts, emails, replies, etc.) whenever relevant.\n\n"
                )
                for doc in docs:
                    knowledge_str += f"\n--- {doc.doc_type} ({doc.department}) ---\n{doc.content}\n"
                
                if system_prompt:
                    if "Company Guidelines & Knowledge Base:" not in system_prompt:
                        system_prompt = f"{system_prompt}\n\n{knowledge_str}"
                else:
                    system_prompt = f"You are a helpful AI assistant operating as part of OctaOS.\n\n{knowledge_str}"
        except Exception as ke:
            import logging
            logging.error(f"Failed to query knowledge base for injection: {ke}")

        inferred_complexity = "low"
        if model and any(w in model.lower() for w in ["sonnet", "gpt-4o", "pro", "large"]):
            inferred_complexity = "high"
        elif any(w in combined_text for w in ["evaluate", "reasoning", "boardroom", "meeting", "analyze", "strategy"]):
            inferred_complexity = "high"

        inferred_realtime = False
        if inferred_task_type == "support" or "whatsapp" in combined_text or "instant" in combined_text:
            inferred_realtime = True

        inferred_bulk = False
        if "generate_campaign" in combined_text or "bulk" in combined_text:
            inferred_bulk = True

        # If a specific non-default model is requested, pass it.
        # Otherwise, pass None to trigger dynamic optimization routing.
        req_provider = provider
        req_model = model
        
        # If the user passed default model/provider strings from old code, let the gateway route
        if model in ["claude-3-haiku-20240307", "gpt-4o", "gemini-2.5-flash", "gemini-1.5-flash", "grok-2"]:
            req_model = None
            req_provider = None

        return await ai_gateway.executeCached(
            db=self.db,
            tenant_id=self.tenant_id,
            prompt=prompt,
            model=req_model,
            provider=req_provider,
            system_prompt=system_prompt,
            task_type=inferred_task_type,
            realtime=inferred_realtime,
            complexity=inferred_complexity,
            bulk=inferred_bulk,
            **kwargs
        )


    async def generate_image(self, prompt: str, provider: str = "openai") -> str:
        # Normalize provider aliases
        if provider in ("dalle", "dall-e", "dall-e-3"):
            provider = "openai"
        elif provider in ("claude"):
            provider = "anthropic"
        elif provider in ("stable", "stability", "stable-diffusion", "sdxl"):
            provider = "stability"

        api_key = self._get_api_key(provider)
        
        if not api_key:
            error_msg = (
                f"error:No API key configured for image provider '{provider}'. "
                f"Go to Settings \u2192 API Keys and add your {provider.title()} key to enable AI image generation."
            )
            import logging
            logging.warning(f"[ImageGen] {error_msg}")
            return error_msg

        try:
            async with httpx.AsyncClient() as client:
                if provider == "openai":
                    response = await client.post(
                        "https://api.openai.com/v1/images/generations",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "dall-e-3",
                            "prompt": prompt,
                            "n": 1,
                            "size": "1024x1024"
                        },
                        timeout=60.0
                    )
                    if response.status_code == 200:
                        url = response.json()["data"][0]["url"]
                        return await ensure_public_url(url, prefix="img") or url
                    else:
                        raise Exception(f"OpenAI DALL-E 3 returned HTTP {response.status_code}: {response.text}")
                elif provider == "anthropic":
                    # Claude generates high-quality SVG code, which we convert to PNG locally
                    system_instructions = (
                        "You are an expert SVG designer. Your job is to create visually stunning, "
                        "modern, clean, and fully-coded SVG illustrations based on the user's description. "
                        "You must ONLY output the raw XML SVG element (starting with <svg and ending with </svg>). "
                        "Do not explain your work, do not use markdown code blocks, do not wrap it in backticks, "
                        "and do not output any text before or after the SVG. "
                        "Use high-quality gradients, shadows, paths, and groups to make the image look professional, "
                        "premium, and complete. Keep the code optimized and compact so it does not get truncated."
                    )
                    
                    models_to_try = [
                        "claude-sonnet-4-6",
                        "claude-opus-4-8",
                        "claude-opus-4-7",
                        "claude-opus-4-6",
                        "claude-haiku-4-5-20251001",
                        "claude-sonnet-4-5-20250929",
                        "claude-3-5-sonnet-latest",
                        "claude-3-5-sonnet-20241022",
                        "claude-3-5-haiku-latest",
                        "claude-3-5-haiku-20241022",
                        "claude-3-haiku-20240307",
                        "claude-3-opus-20240229"
                    ]
                    
                    response = None
                    last_err = ""
                    
                    for model_name in models_to_try:
                        try:
                            response = await client.post(
                                "https://api.anthropic.com/v1/messages",
                                headers={
                                    "x-api-key": api_key,
                                    "anthropic-version": "2023-06-01",
                                    "content-type": "application/json"
                                },
                                json={
                                    "model": model_name,
                                    "max_tokens": 4096,
                                    "system": system_instructions,
                                    "messages": [{
                                        "role": "user",
                                        "content": f"Create a detailed, visually rich square 1:1 SVG graphic for: {prompt}. Ensure it has viewBox=\"0 0 800 800\"."
                                    }]
                                },
                                timeout=90.0
                            )
                            if response.status_code == 200:
                                break
                            else:
                                err_data = response.json()
                                err_msg = err_data.get("error", {}).get("message", response.text)
                                last_err = f"HTTP {response.status_code}: {err_msg}"
                                # If it's a 404/not found error or invalid model, try the next model
                                if response.status_code == 404 or "model" in err_msg.lower() or "not_found" in err_msg.lower():
                                    import logging
                                    logging.warning(f"Anthropic model {model_name} failed: {last_err}. Trying next model...")
                                    continue
                                else:
                                    # Other error (like authentication, rate limit), raise immediately
                                    raise Exception(last_err)
                        except Exception as exc:
                            last_err = str(exc)
                            # If it's a connection/timeout error or other exception, try next model
                            import logging
                            logging.warning(f"Anthropic model {model_name} exception: {last_err}. Trying next model...")
                            continue
                    
                    if not response or response.status_code != 200:
                        raise Exception(f"Anthropic API error (all models failed). Last error: {last_err}")
                    
                    res_json = response.json()
                    raw_text = res_json["content"][0]["text"].strip()
                    
                    import re
                    svg_match = re.search(r"<svg.*?</svg>", raw_text, re.DOTALL | re.IGNORECASE)
                    if svg_match:
                        svg_code = svg_match.group(0).strip()
                    else:
                        # Fallback for truncated outputs (missing closing tag)
                        start_match = re.search(r"<svg.*", raw_text, re.DOTALL | re.IGNORECASE)
                        if start_match:
                            svg_code = start_match.group(0).strip()
                            if "</svg>" not in svg_code.lower():
                                svg_code += "\n</svg>"
                        else:
                            raise Exception(
                                f"Claude responded, but no valid SVG tag was found in the output: {raw_text[:200]}..."
                            )
                    
                    # Convert SVG to PNG using cairosvg
                    try:
                        import cairosvg
                        png_bytes = cairosvg.svg2png(bytestring=svg_code.encode("utf-8"))
                        png_b64 = base64.b64encode(png_bytes).decode("utf-8")
                        data_url = f"data:image/png;base64,{png_b64}"
                        return await ensure_public_url(data_url, prefix="img") or data_url
                    except Exception as e:
                        # Fallback: return SVG data URL directly
                        svg_b64 = base64.b64encode(svg_code.encode("utf-8")).decode("utf-8")
                        data_url = f"data:image/svg+xml;base64,{svg_b64}"
                        return await ensure_public_url(data_url, prefix="img") or data_url
                elif provider == "gemini":
                    # Google Imagen 4.0 predict API
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={api_key}"
                    payload = {
                        "instances": [{"prompt": prompt}],
                        "parameters": {"aspectRatio": "1:1", "numberOfImages": 1}
                    }
                    response = await client.post(url, json=payload, timeout=60.0)
                    if response.status_code == 200:
                        res_data = response.json()
                        pred = res_data["predictions"][0]
                        img_b64 = pred["bytesBase64Encoded"]
                        mime_type = pred.get("mimeType", "image/jpeg")
                        data_url = f"data:{mime_type};base64,{img_b64}"
                        return await ensure_public_url(data_url, prefix="img") or data_url
                    else:
                        raise Exception(f"Gemini Imagen API returned status {response.status_code}: {response.text}")

                elif provider == "grok":
                    # xAI Grok Image Generation
                    response = await client.post(
                        "https://api.x.ai/v1/images/generations",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "grok-2-image-gen",
                            "prompt": prompt,
                            "n": 1,
                            "size": "1024x1024"
                        },
                        timeout=60.0
                    )
                    if response.status_code == 200:
                        url = response.json()["data"][0]["url"]
                        return await ensure_public_url(url, prefix="img") or url
                    else:
                        raise Exception(f"Grok API returned status {response.status_code}: {response.text}")
                elif provider == "stability":
                    # Stability AI — Stable Diffusion XL via REST API v1
                    response = await client.post(
                        "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Accept": "application/json",
                            "Content-Type": "application/json"
                        },
                        json={
                            "text_prompts": [{"text": prompt, "weight": 1.0}],
                            "cfg_scale": 7,
                            "height": 1024,
                            "width": 1024,
                            "steps": 30,
                            "samples": 1
                        },
                        timeout=90.0
                    )
                    if response.status_code == 200:
                        import base64 as _base64
                        artifacts = response.json().get("artifacts", [])
                        if not artifacts:
                            raise Exception("Stability AI returned no artifacts.")
                        img_b64 = artifacts[0]["base64"]
                        data_url = f"data:image/png;base64,{img_b64}"
                        return await ensure_public_url(data_url, prefix="img") or data_url
                    else:
                        raise Exception(f"Stability AI API returned status {response.status_code}: {response.text}")
        except Exception as e:
            import logging
            error_msg = str(e)
            logging.error(f"[ImageGen] Provider '{provider}' failed: {error_msg}")
            try:
                from app.models.agents import ActivityLog
                log = ActivityLog(
                    tenant_id=self.tenant_id,
                    agent_name="Marketing AI",
                    action="Image Generation Failed",
                    description=f"Provider '{provider}': {error_msg}",
                    status="failed"
                )
                self.db.add(log)
                self.db.commit()
            except Exception:
                pass
            # Return a sentinel so callers can display the real error in the UI
            return f"error:{error_msg}"

    async def _poll_pika_job(self, client: httpx.AsyncClient, job_id: str, api_key: str, fallback: str, max_attempts: int = 30) -> str:
        import asyncio
        for _ in range(max_attempts):
            resp = await client.get(
                f"https://api.pika.art/v1/generate/{job_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "")
                if status == "completed" and data.get("video_url"):
                    return data["video_url"]
                if status in ("failed", "error"):
                    raise Exception(data.get("error", "Pika generation failed"))
            await asyncio.sleep(5)
        return fallback

    async def generate_video(self, prompt: str, provider: str = "pika") -> str:
        api_key = self._get_api_key(provider)
        if not api_key:
            error_msg = (
                f"error:No API key configured for video provider '{provider}'. "
                f"Go to Settings \u2192 API Keys and add your {provider.title()} key to enable AI video generation."
            )
            import logging
            logging.warning(f"[VideoGen] {error_msg}")
            try:
                from app.models.agents import ActivityLog
                log = ActivityLog(
                    tenant_id=self.tenant_id,
                    agent_name="Marketing AI",
                    action="Media Generation Warning",
                    description=f"API key for video provider '{provider}' is not configured.",
                    status="failed"
                )
                self.db.add(log)
                self.db.commit()
            except Exception as log_err:
                import logging as _l
                _l.error(f"Failed to log missing API key warning: {log_err}")
            return error_msg

        try:
            async with httpx.AsyncClient() as client:
                if provider == "pika":
                    response = await client.post(
                        "https://api.pika.art/v1/generate",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"prompt": prompt, "options": {"aspect_ratio": "16:9"}},
                        timeout=40.0,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("video_url"):
                            url = data["video_url"]
                        elif data.get("id"):
                            url = await self._poll_pika_job(client, data["id"], api_key, None)
                            if not url:
                                raise Exception("Pika job did not return a video URL.")
                        else:
                            raise Exception("Pika API did not return a video URL or job ID.")
                        return await ensure_public_url(url, prefix="vid", default_mime="video/mp4") or url
                    raise Exception(f"Pika API error: {response.text}")

                elif provider in ("veo", "google"):
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/veo-2.0-generate-001:predict?key={api_key}"
                    payload = {
                        "instances": [{"prompt": prompt}],
                        "parameters": {"video_length": "SHORT"},
                    }
                    response = await client.post(url, json=payload, timeout=60.0)
                    if response.status_code == 200:
                        pred = response.json()["predictions"][0]
                        vid_b64 = pred.get("bytesBase64Encoded")
                        mime_type = pred.get("mimeType", "video/mp4")
                        if vid_b64:
                            data_url = f"data:{mime_type};base64,{vid_b64}"
                            return await ensure_public_url(data_url, prefix="vid", default_mime="video/mp4") or data_url
                    raise Exception(f"Veo API error: {response.text}")

                elif provider == "grok":
                    response = await client.post(
                        "https://api.x.ai/v1/videos/generations",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"model": "grok-video-gen", "prompt": prompt},
                        timeout=40.0,
                    )
                    if response.status_code == 200:
                        url = response.json()["data"][0].get("url")
                        if not url:
                            raise Exception("Grok Video API did not return a video URL.")
                        return await ensure_public_url(url, prefix="vid", default_mime="video/mp4") or url
                    raise Exception(f"Grok Video API error: {response.text}")

                elif provider in ("stable", "stability", "stable-video"):
                    response = await client.post(
                        "https://api.stability.ai/v2beta/text-to-video",
                        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                        data={"prompt": prompt},
                        timeout=60.0,
                    )
                    if response.status_code == 200:
                        url = response.json().get("video_url")
                        if not url:
                            raise Exception("Stability AI did not return a video URL.")
                        return await ensure_public_url(url, prefix="vid", default_mime="video/mp4") or url
                    raise Exception(f"Stable Video API error: {response.text}")

                else:
                    raise ValueError(
                        f"Video provider '{provider}' is not supported. "
                        f"Please configure a valid video provider key (pika, veo, grok, stability)."
                    )
        except Exception as e:
            import logging
            error_msg = str(e)
            logging.error(f"[VideoGen] Provider '{provider}' failed: {error_msg}")
            try:
                from app.models.agents import ActivityLog
                log = ActivityLog(
                    tenant_id=self.tenant_id,
                    agent_name="Marketing AI",
                    action="Media Generation Failed",
                    description=f"Video generation failed via provider '{provider}': {error_msg}.",
                    status="failed",
                )
                self.db.add(log)
                self.db.commit()
            except Exception as log_err:
                logging.error(f"Failed to log video generation failure: {log_err}")
            return f"error:{error_msg}"
