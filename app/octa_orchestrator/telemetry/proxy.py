import time
import uuid
import json
import httpx
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Response, BackgroundTasks
from app.octa_orchestrator.telemetry.sanitizer import DataSanitizer

router = APIRouter(prefix="/v1/telemetry", tags=["LLM Telemetry Proxy"])
sanitizer = DataSanitizer()

UPSTREAM_LLM_URL = "https://api.openai.com/v1/chat/completions"

async def async_save_trajectory_event(
    trajectory_id: str,
    user_id: Optional[str],
    clean_request: Dict[str, Any],
    clean_response: Dict[str, Any],
    latency_ms: int
):
    """Background task saving sanitized LLM interaction tokens for future SLM training."""
    # In production, this pushes to PostgreSQL / ClickHouse / S3
    print(f"[Telemetry Logged] Trajectory ID: {trajectory_id} | Latency: {latency_ms}ms")
    usage = clean_response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    # Store trajectory event structure
    event_record = {
        "trajectory_id": trajectory_id,
        "user_id": user_id,
        "request": clean_request,
        "response": clean_response,
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens
    }
    # Writes to cloud storage or queue
    return event_record

@router.post("/chat/completions")
async def telemetry_proxy_completion(request: Request, background_tasks: BackgroundTasks):
    """Proxy endpoint that intercepts tokens, sanitizes PII, and forwards to upstream LLM."""
    start_time = time.time()
    raw_body = await request.json()
    headers = dict(request.headers)
    
    trajectory_id = headers.get("x-trajectory-id", str(uuid.uuid4()))
    user_id = headers.get("x-user-id", "anonymous")
    
    # 1. Sanitize request
    clean_request = sanitizer.sanitize_payload(raw_body)
    
    # 2. Forward request to upstream target LLM
    auth_header = headers.get("authorization", "")
    target_headers = {"Content-Type": "application/json"}
    if auth_header:
        target_headers["Authorization"] = auth_header

    async with httpx.AsyncClient() as client:
        upstream_res = await client.post(
            UPSTREAM_LLM_URL,
            json=raw_body,
            headers=target_headers,
            timeout=60.0
        )
        
        try:
            response_json = upstream_res.json()
        except Exception:
            response_json = {"error": "Invalid response format", "status": upstream_res.status_code}

    latency_ms = int((time.time() - start_time) * 1000)
    
    # 3. Sanitize response and queue async telemetry storage
    clean_response = sanitizer.sanitize_payload(response_json)
    background_tasks.add_task(
        async_save_trajectory_event,
        trajectory_id,
        user_id,
        clean_request,
        clean_response,
        latency_ms
    )
    
    return Response(
        content=upstream_res.content,
        status_code=upstream_res.status_code,
        headers={"Content-Type": "application/json", "x-trajectory-id": trajectory_id}
    )
