from celery import Celery
from app.core.config import settings
import os
from kombu import Queue, Exchange
import logging
from celery.signals import task_failure

logger = logging.getLogger(__name__)

broker_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
if os.getenv("TESTING"):
    broker_url = "memory://"

celery_app = Celery("worker", broker=broker_url)

# Define Exchanges & Queues for DLQ (Dead Letter Queue) support
main_exchange = Exchange("main", type="direct")
dlq_exchange = Exchange("dlq", type="direct")

celery_app.conf.task_queues = (
    Queue("main-queue", main_exchange, routing_key="main"),
    Queue("dead-letter-queue", dlq_exchange, routing_key="dlq"),
)

celery_app.conf.task_default_queue = "main-queue"
celery_app.conf.task_default_exchange = "main"
celery_app.conf.task_default_routing_key = "main"

celery_app.conf.task_routes = {
    "app.worker.tasks.*": "main-queue",
}

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "daily-autonomous-operations": {
        "task": "run_daily_operations",
        "schedule": crontab(hour=8, minute=0),
    },
    "poll-workflows": {
        "task": "poll_and_execute_workflows",
        "schedule": crontab(minute="*"),
    },
    "publish-scheduled-posts": {
        "task": "publish_scheduled_posts",
        "schedule": crontab(minute="*/5"),
    },
    "sales-meeting-reminders": {
        "task": "send_sales_meeting_reminders",
        "schedule": crontab(minute="*/5"),
    },
    "poll-gmail-sales-inbox": {
        "task": "poll_gmail_sales_inbox",
        "schedule": crontab(minute="*/3"),
    },
    "sync-marketing-insights": {
        "task": "sync_marketing_insights_task",
        "schedule": crontab(minute="20", hour="*/6"),  # every 6 hours
    },
}

if os.getenv("TESTING"):
    celery_app.conf.task_always_eager = True

# Hook to capture Celery job failures and route them to DLQ
@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, traceback=None, args=None, kwargs=None, einfo=None, **kwargs_extra):
    task_name = sender.name if sender else "unknown"
    logger.error(
        f"Celery task failure detected: {task_name} (ID: {task_id}) failed: {exception}",
        exc_info=True
    )
    try:
        celery_app.send_task(
            "dead_letter_handler",
            args=[task_name, task_id, str(exception), str(args), str(kwargs)],
            queue="dead-letter-queue"
        )
    except Exception as route_err:
        logger.error(f"Failed to route task failure to DLQ queue: {route_err}")

