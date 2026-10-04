import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import AsyncGenerator, Dict, Optional, Set, Any
from sqlalchemy.orm import Session

from app.models.executive import WorkflowEvent

logger = logging.getLogger(__name__)

class SSEManager:
    """
    Enterprise Real-Time Event Streaming Manager.
    Supports:
    - Real-time Pub/Sub distribution to connected clients
    - Replay of missed events via Last-Event-ID / sequence_num
    - Periodic heartbeats (: ping\n\n) to keep connections alive through reverse proxies
    - Automatic DB fallback polling for multi-worker architectures
    """
    _subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)

    @classmethod
    def subscribe(cls, workflow_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        cls._subscribers[workflow_id].add(q)
        return q

    @classmethod
    def unsubscribe(cls, workflow_id: str, q: asyncio.Queue):
        if workflow_id in cls._subscribers:
            cls._subscribers[workflow_id].discard(q)
            if not cls._subscribers[workflow_id]:
                del cls._subscribers[workflow_id]

    @classmethod
    def publish(cls, workflow_id: str, event_data: Dict[str, Any]):
        """
        Broadcasts an event dict to all active in-process listeners for this workflow.
        """
        if workflow_id in cls._subscribers:
            for q in list(cls._subscribers[workflow_id]):
                try:
                    q.put_nowait(event_data)
                except Exception as e:
                    logger.debug(f"Failed to push to SSE subscriber queue: {e}")

    @staticmethod
    def format_sse_message(event_id: Any, event_type: str, data: Any) -> str:
        data_str = json.dumps(data) if not isinstance(data, str) else data
        return f"id: {event_id}\nevent: {event_type}\ndata: {data_str}\n\n"

    @classmethod
    async def event_generator(
        cls,
        db_factory,
        tenant_id: str,
        workflow_id: str,
        last_event_id: Optional[int] = None,
        poll_interval: float = 1.0,
        heartbeat_interval: float = 15.0
    ) -> AsyncGenerator[str, None]:
        """
        Streams events for a workflow.
        First replays events after last_event_id, then streams real-time events.
        Emits SSE keep-alive comments when idle.
        """
        current_seq = int(last_event_id) if last_event_id is not None else 0
        last_heartbeat = time.time()

        # Phase 1: Replay backlog from DB
        session: Session = db_factory()
        try:
            backlog = session.query(WorkflowEvent).filter(
                WorkflowEvent.tenant_id == tenant_id,
                WorkflowEvent.workflow_id == workflow_id,
                WorkflowEvent.sequence_num > current_seq
            ).order_by(WorkflowEvent.sequence_num.asc()).all()

            for ev in backlog:
                current_seq = ev.sequence_num
                payload = json.loads(ev.canonical_payload) if isinstance(ev.canonical_payload, str) else ev.canonical_payload
                msg_data = {
                    "sequence_num": ev.sequence_num,
                    "event_type": ev.event_type,
                    "actor_type": ev.actor_type,
                    "actor_id": ev.actor_id,
                    "task_id": ev.task_id,
                    "payload": payload,
                    "event_hash": ev.event_hash,
                    "created_at": ev.timestamp_iso
                }
                yield cls.format_sse_message(ev.sequence_num, ev.event_type, msg_data)
                last_heartbeat = time.time()
        finally:
            session.close()

        # Phase 2: Real-time stream with DB fallback & heartbeat
        queue = cls.subscribe(workflow_id)
        try:
            while True:
                try:
                    # Wait for real-time push with a timeout
                    event_data = await asyncio.wait_for(queue.get(), timeout=poll_interval)
                    seq = event_data.get("sequence_num", 0)
                    if seq > current_seq:
                        current_seq = seq
                        yield cls.format_sse_message(seq, event_data.get("event_type", "message"), event_data)
                        last_heartbeat = time.time()
                except asyncio.TimeoutError:
                    # Check DB for events committed by other workers/processes
                    check_session: Session = db_factory()
                    try:
                        new_events = check_session.query(WorkflowEvent).filter(
                            WorkflowEvent.tenant_id == tenant_id,
                            WorkflowEvent.workflow_id == workflow_id,
                            WorkflowEvent.sequence_num > current_seq
                        ).order_by(WorkflowEvent.sequence_num.asc()).all()

                        for ev in new_events:
                            current_seq = ev.sequence_num
                            payload = json.loads(ev.canonical_payload) if isinstance(ev.canonical_payload, str) else ev.canonical_payload
                            msg_data = {
                                "sequence_num": ev.sequence_num,
                                "event_type": ev.event_type,
                                "actor_type": ev.actor_type,
                                "actor_id": ev.actor_id,
                                "task_id": ev.task_id,
                                "payload": payload,
                                "event_hash": ev.event_hash,
                                "created_at": ev.timestamp_iso
                            }
                            yield cls.format_sse_message(ev.sequence_num, ev.event_type, msg_data)
                            last_heartbeat = time.time()
                    finally:
                        check_session.close()

                    # Send heartbeat if idle
                    if time.time() - last_heartbeat >= heartbeat_interval:
                        yield ": ping\n\n"
                        last_heartbeat = time.time()
        except asyncio.CancelledError:
            logger.info(f"SSE client disconnected for workflow {workflow_id}")
            raise
        finally:
            cls.unsubscribe(workflow_id, queue)
