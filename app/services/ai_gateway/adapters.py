import httpx
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class BaseProviderAdapter:
    def __init__(self, api_key: str = "", config: Dict[str, Any] = None):
        self.api_key = api_key
        self.config = config or {}

    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        """
        Executes a completion request.
        Returns: {
            "content": str,
            "input_tokens": int,
            "output_tokens": int,
            "cached_tokens": int,
            "raw_response": Any
        }
        """
        raise NotImplementedError()

    def supports_native_caching(self, model: str) -> bool:
        return False

    def supports_native_batching(self, model: str) -> bool:
        return False

    async def submit_native_batch(self, tasks: List[Dict[str, Any]], model: str) -> str:
        """
        Submits tasks for batch execution natively. Returns provider batch ID.
        """
        raise NotImplementedError("Native batching not supported by this provider.")

    async def check_native_batch_status(self, provider_batch_id: str) -> Dict[str, Any]:
        """
        Checks native batch status. Returns:
        {
            "status": "pending" | "completed" | "failed",
            "completed_tasks": int,
            "total_tasks": int,
            "results": List[Dict[str, Any]] (if completed)
        }
        """
        raise NotImplementedError("Native batching not supported by this provider.")


class OpenAIAdapter(BaseProviderAdapter):
    def supports_native_caching(self, model: str) -> bool:
        return True # OpenAI automatically caches prompts > 1024 tokens

    def supports_native_batching(self, model: str) -> bool:
        return True

    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        images = kwargs.pop("images", None)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            user_content = [{"type": "text", "text": prompt}]
            for img in images:
                mime = img.get("mime_type", "image/png")
                b64 = img.get("data", "")
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": prompt})

        # Allow extra parameters like temperature
        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30.0
            )
            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            
            # OpenAI tracks cached tokens in prompt_tokens_details
            cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "raw_response": data
            }

    async def submit_native_batch(self, tasks: List[Dict[str, Any]], model: str) -> str:
        # 1. Create a JSONL input file payload
        jsonl_lines = []
        for i, t in enumerate(tasks):
            req = {
                "custom_id": f"task-{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": t.get("system_prompt", "")},
                        {"role": "user", "content": t.get("prompt", "")}
                    ],
                    **t.get("kwargs", {})
                }
            }
            jsonl_lines.append(json.dumps(req))
        file_content = "\n".join(jsonl_lines)

        async with httpx.AsyncClient() as client:
            # 2. Upload file
            files = {"file": ("input.jsonl", file_content, "application/jsonl")}
            data = {"purpose": "batch"}
            upload_res = await client.post(
                "https://api.openai.com/v1/files",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data=data,
                timeout=30.0
            )
            if upload_res.status_code != 200:
                raise Exception(f"OpenAI File Upload failed: {upload_res.text}")
            file_id = upload_res.json()["id"]

            # 3. Create batch job
            batch_res = await client.post(
                "https://api.openai.com/v1/batches",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input_file_id": file_id,
                    "endpoint": "/v1/chat/completions",
                    "completion_window": "24h"
                },
                timeout=30.0
            )
            if batch_res.status_code != 200:
                raise Exception(f"OpenAI Batch creation failed: {batch_res.text}")
            
            return batch_res.json()["id"]

    async def check_native_batch_status(self, provider_batch_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"https://api.openai.com/v1/batches/{provider_batch_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=20.0
            )
            if res.status_code != 200:
                raise Exception(f"OpenAI check batch failed: {res.text}")
            
            data = res.json()
            status = data.get("status")
            
            total = data.get("request_counts", {}).get("total", 0)
            completed = data.get("request_counts", {}).get("completed", 0)
            failed = data.get("request_counts", {}).get("failed", 0)
            
            normalized_status = "pending"
            if status in ["completed"]:
                normalized_status = "completed"
            elif status in ["failed", "expired", "cancelled"]:
                normalized_status = "failed"

            results = []
            if normalized_status == "completed":
                # Retrieve output file
                output_file_id = data.get("output_file_id")
                if output_file_id:
                    file_res = await client.get(
                        f"https://api.openai.com/v1/files/{output_file_id}/content",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=30.0
                    )
                    if file_res.status_code == 200:
                        for line in file_res.text.strip().split("\n"):
                            if not line:
                                continue
                            item = json.loads(line)
                            custom_id = item.get("custom_id")
                            # Extract response
                            response_body = item.get("response", {}).get("body", {})
                            content = response_body.get("choices", [{}])[0].get("message", {}).get("content", "")
                            usage = response_body.get("usage", {})
                            results.append({
                                "custom_id": custom_id,
                                "content": content,
                                "input_tokens": usage.get("prompt_tokens", 0),
                                "output_tokens": usage.get("completion_tokens", 0),
                                "status": "success"
                            })

            return {
                "status": normalized_status,
                "completed_tasks": completed,
                "total_tasks": total,
                "results": results
            }


class AnthropicAdapter(BaseProviderAdapter):
    def supports_native_caching(self, model: str) -> bool:
        return True # Anthropic supports prompt caching explicitly via cache_control

    def supports_native_batching(self, model: str) -> bool:
        return True

    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        images = kwargs.pop("images", None)
        if images:
            user_content = [{"type": "text", "text": prompt}]
            for img in images:
                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("mime_type", "image/png"),
                        "data": img.get("data", "")
                    }
                })
            messages = [{"role": "user", "content": user_content}]
        else:
            messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": messages,
        }

        # Add native prompt caching tags if prompt is large
        if system_prompt:
            # If the system prompt is long, we add cache_control to it
            if len(system_prompt) > 1000:
                payload["system"] = [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            else:
                payload["system"] = system_prompt

        # Clean kwargs
        for k, v in kwargs.items():
            if k != "max_tokens":
                payload[k] = v

        # Fallback list of models if requested model is 404
        models_to_try = [model]
        fallbacks = [
            "claude-sonnet-4-6",
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-5-20250929",
            "claude-3-5-sonnet-latest",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-latest",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229"
        ]
        for f in fallbacks:
            if f not in models_to_try:
                models_to_try.append(f)

        response = None
        last_err = ""
        used_model = model

        async with httpx.AsyncClient() as client:
            for m in models_to_try:
                payload["model"] = m
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=30.0
                )
                if response.status_code == 200:
                    used_model = m
                    break
                else:
                    try:
                        err_data = response.json()
                        err_msg = err_data.get("error", {}).get("message", response.text)
                    except Exception:
                        err_msg = response.text
                    last_err = f"HTTP {response.status_code}: {err_msg}"
                    
                    # Try next model if 404 model not found
                    if response.status_code == 404 or "model" in err_msg.lower() or "not_found" in err_msg.lower():
                        logger.warning(f"Anthropic model {m} not available ({last_err}). Trying fallback...")
                        continue
                    else:
                        raise Exception(f"Anthropic API error: {last_err}")
            
            if not response or response.status_code != 200:
                raise Exception(f"Anthropic API error (all models failed). Last error: {last_err}")

            data = response.json()
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            # Retrieve cache tokens from anthropic usage headers
            cached_read = usage.get("cache_read_tokens", 0)
            cached_creation = usage.get("cache_creation_tokens", 0)
            cached_tokens = cached_read + cached_creation

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "raw_response": data
            }

    async def submit_native_batch(self, tasks: List[Dict[str, Any]], model: str) -> str:
        # Anthropic message batches API
        requests = []
        for i, t in enumerate(tasks):
            req = {
                "custom_id": f"task-{i}",
                "params": {
                    "model": model,
                    "max_tokens": t.get("kwargs", {}).get("max_tokens", 1024),
                    "messages": [{"role": "user", "content": t.get("prompt", "")}]
                }
            }
            if t.get("system_prompt"):
                req["params"]["system"] = t.get("system_prompt")
            requests.append(req)

        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages/batches",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                    "anthropic-beta": "message-batches-2024-09-24"
                },
                json={"requests": requests},
                timeout=30.0
            )
            if res.status_code != 200:
                raise Exception(f"Anthropic Batch creation failed: {res.text}")
            
            return res.json()["id"]

    async def check_native_batch_status(self, provider_batch_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"https://api.anthropic.com/v1/messages/batches/{provider_batch_id}",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "message-batches-2024-09-24"
                },
                timeout=20.0
            )
            if res.status_code != 200:
                raise Exception(f"Anthropic check batch failed: {res.text}")
            
            data = res.json()
            status = data.get("processing_status") # processing, ended
            
            total = data.get("request_counts", {}).get("total", 0)
            processing = data.get("request_counts", {}).get("processing", 0)
            succeeded = data.get("request_counts", {}).get("succeeded", 0)
            failed = data.get("request_counts", {}).get("failed", 0)
            completed = succeeded + failed
            
            normalized_status = "pending"
            if status == "ended":
                normalized_status = "completed"
            
            results = []
            if normalized_status == "completed":
                # Download batch results stream
                results_url = data.get("results_url")
                if results_url:
                    stream_res = await client.get(results_url, timeout=30.0)
                    if stream_res.status_code == 200:
                        for line in stream_res.text.strip().split("\n"):
                            if not line:
                                continue
                            item = json.loads(line)
                            custom_id = item.get("custom_id")
                            result_type = item.get("result", {}).get("type")
                            if result_type == "succeeded":
                                message = item["result"]["message"]
                                content = message["content"][0]["text"]
                                usage = message.get("usage", {})
                                results.append({
                                    "custom_id": custom_id,
                                    "content": content,
                                    "input_tokens": usage.get("input_tokens", 0),
                                    "output_tokens": usage.get("output_tokens", 0),
                                    "status": "success"
                                })
                            else:
                                results.append({
                                    "custom_id": custom_id,
                                    "content": "",
                                    "input_tokens": 0,
                                    "output_tokens": 0,
                                    "status": "failed"
                                })
            
            return {
                "status": normalized_status,
                "completed_tasks": completed,
                "total_tasks": total,
                "results": results
            }


class GeminiAdapter(BaseProviderAdapter):
    def supports_native_caching(self, model: str) -> bool:
        return True

    def supports_native_batching(self, model: str) -> bool:
        return False # No native batch API in Gemini SDK at beta endpoint

    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        images = kwargs.pop("images", None)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        
        parts: List[Dict[str, Any]] = [{"text": prompt}]
        if images:
            for img in images:
                parts.append({
                    "inline_data": {
                        "mime_type": img.get("mime_type", "image/png"),
                        "data": img.get("data", "")
                    }
                })

        payload = {
            "contents": [{"parts": parts}]
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        # Add parameter overrides
        generation_config = {}
        for k in ["temperature", "topP", "topK", "maxOutputTokens"]:
            if k in kwargs:
                generation_config[k] = kwargs[k]
        if generation_config:
            payload["generationConfig"] = generation_config

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            if response.status_code != 200:
                raise Exception(f"Gemini API error: {response.text}")

            data = response.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount", 0)
            output_tokens = usage.get("candidatesTokenCount", 0)
            
            # Gemini caches system instructions automatically if context caching is active
            cached_tokens = usage.get("cachedContentTokenCount", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "raw_response": data
            }


class OpenRouterAdapter(BaseProviderAdapter):
    def supports_native_caching(self, model: str) -> bool:
        # OpenRouter automatically routes prompt caching for models that support it
        return True

    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        images = kwargs.pop("images", None)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            user_content = [{"type": "text", "text": prompt}]
            for img in images:
                mime = img.get("mime_type", "image/png")
                b64 = img.get("data", "")
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://octaos.ai",
            "X-Title": "OctaOS",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=45.0
            )
            if response.status_code != 200:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message") or err_json.get("message") or response.text
                except Exception:
                    err_msg = response.text
                raise Exception(f"OpenRouter API error (status {response.status_code}): {err_msg}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise Exception(f"OpenRouter API returned no choices: {data}")
            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            cached_tokens = (
                usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                or usage.get("cache_discount", 0)
            )

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "raw_response": data
            }


class TogetherAdapter(BaseProviderAdapter):
    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=45.0
            )
            if response.status_code != 200:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message") or err_json.get("message") or response.text
                except Exception:
                    err_msg = response.text
                raise Exception(f"Together AI API error (status {response.status_code}): {err_msg}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise Exception(f"Together AI API returned no choices: {data}")
            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "raw_response": data
            }


class GrokAdapter(BaseProviderAdapter):
    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=45.0
            )
            if response.status_code != 200:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message") or err_json.get("message") or response.text
                except Exception:
                    err_msg = response.text
                raise Exception(f"Grok API error (status {response.status_code}): {err_msg}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise Exception(f"Grok API returned no choices: {data}")
            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "raw_response": data
            }


class GroqAdapter(BaseProviderAdapter):
    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30.0
            )
            if response.status_code != 200:
                raise Exception(f"Groq API error: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "raw_response": data
            }


class MistralAdapter(BaseProviderAdapter):
    def supports_native_batching(self, model: str) -> bool:
        return False  # Native batch API not yet implemented for Mistral

    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30.0
            )
            if response.status_code != 200:
                raise Exception(f"Mistral API error: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "raw_response": data
            }


class CohereAdapter(BaseProviderAdapter):
    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        # Using Cohere v1 API
        payload = {
            "model": model,
            "message": prompt,
        }
        if system_prompt:
            payload["preamble"] = system_prompt

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.cohere.ai/v1/chat",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30.0
            )
            if response.status_code != 200:
                raise Exception(f"Cohere API error: {response.text}")

            data = response.json()
            content = data.get("text", "")
            
            # Cohere usage details
            meta = data.get("meta", {})
            tokens = meta.get("tokens", {})
            input_tokens = tokens.get("input_tokens", 0)
            output_tokens = tokens.get("output_tokens", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "raw_response": data
            }


class LocalAdapter(BaseProviderAdapter):
    async def execute_request(self, prompt: str, model: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        # Routes requests to local self-hosted inference servers (Ollama or vLLM compatible OpenAI endpoint)
        endpoint = self.config.get("local_endpoint", "http://localhost:11434/v1/chat/completions")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=40.0
            )
            if response.status_code != 200:
                raise Exception(f"Local model error: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "raw_response": data
            }
