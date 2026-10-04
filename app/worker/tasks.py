from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.verticals.sales import SalesService
from app.services.media.storage import ensure_public_url
from asgiref.sync import async_to_sync

@celery_app.task(name="score_lead_task")
def score_lead_task(tenant_id: str, lead_id: str):
    db = SessionLocal()
    try:
        service = SalesService(db, tenant_id)
        async_to_sync(service.score_lead)(lead_id)
    finally:
        db.close()

@celery_app.task(name="enrich_lead_task")
def enrich_lead_task(tenant_id: str, lead_id: str):
    from app.models.verticals import Lead
    from app.models.base import APICredential
    from app.services.llm_gateway import LLMGateway
    from app.core.security import decrypt_api_key
    import httpx

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id).first()
        if not lead:
            return

        enrichment = {}

        # Apollo enrichment when configured
        apollo_cred = db.query(APICredential).filter_by(tenant_id=tenant_id, provider="apollo").first()
        if apollo_cred and apollo_cred.encrypted_key:
            api_key = decrypt_api_key(apollo_cred.encrypted_key)
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        "https://api.apollo.io/v1/people/match",
                        json={"api_key": api_key, "email": lead.email, "reveal_personal_emails": False},
                    )
                    if resp.status_code == 200:
                        person = resp.json().get("person") or {}
                        enrichment["apollo"] = {
                            "title": person.get("title"),
                            "linkedin_url": person.get("linkedin_url"),
                            "seniority": person.get("seniority"),
                            "department": person.get("departments"),
                        }
                        if person.get("organization", {}).get("name"):
                            lead.company = person["organization"]["name"]
                            
                    # Deep Context Enrichment (News & Jobs)
                    domain = ""
                    if lead.email and "@" in lead.email:
                        domain = lead.email.split("@")[-1]
                        
                    if domain:
                        from app.services.agents.sales import SalesAgent
                        agent = SalesAgent(db, tenant_id)
                        org_id = async_to_sync(agent._fetch_apollo_org_data)(api_key, domain)
                        if org_id:
                            news = async_to_sync(agent._fetch_apollo_news)(api_key, org_id)
                            jobs = async_to_sync(agent._fetch_apollo_jobs)(api_key, org_id)
                            if news:
                                enrichment["apollo"]["news"] = news
                            if jobs:
                                enrichment["apollo"]["jobs"] = jobs
            except Exception:
                pass

        # LLM enrichment fallback / supplement
        llm = LLMGateway(db, tenant_id)
        
        news_context = ""
        jobs_context = ""
        if enrichment.get("apollo", {}).get("news"):
            news_context = "Recent News: " + ", ".join([n["title"] for n in enrichment["apollo"]["news"]]) + "\n"
        if enrichment.get("apollo", {}).get("jobs"):
            jobs_context = "Recent Job Openings: " + ", ".join([j["title"] for j in enrichment["apollo"]["jobs"]]) + "\n"
            
        prompt = (
            f"Enrich this B2B lead with professional details as JSON only.\n"
            f"Name: {lead.name}\nEmail: {lead.email}\nCompany: {lead.company}\n"
            f"{news_context}{jobs_context}"
            f"Output keys: title, industry, company_size, pain_points (array), outreach_angle, "
            f"personal_email, company_email, mobile_no, company_contact_no, need_of_what, how_much, why, target_context, priority (one of: low, medium, high)."
        )
        response = async_to_sync(llm.complete)(prompt=prompt, provider="gemini")
        try:
            import json
            cleaned = response.strip().strip("```json").strip("```").strip()
            res_dict = json.loads(cleaned)
            enrichment["llm"] = res_dict
            
            # Directly update empty fields on lead
            if not lead.personal_email:
                lead.personal_email = res_dict.get("personal_email")
            if not lead.company_email:
                lead.company_email = res_dict.get("company_email") or lead.email
            if not lead.mobile_no:
                lead.mobile_no = res_dict.get("mobile_no") or lead.phone
            if not lead.company_contact_no:
                lead.company_contact_no = res_dict.get("company_contact_no")
            if not lead.need_of_what:
                lead.need_of_what = res_dict.get("need_of_what")
            if not lead.how_much:
                lead.how_much = res_dict.get("how_much")
            if not lead.why:
                lead.why = res_dict.get("why")
            if not lead.target_context:
                lead.target_context = res_dict.get("target_context")
            if not lead.priority or lead.priority == "medium":
                lead.priority = res_dict.get("priority", "medium")
        except Exception:
            enrichment["llm"] = {"raw": response[:500]}

        lead.data = {**(lead.data or {}), "enrichment": enrichment}
        if lead.status == "captured":
            lead.status = "enriched"
        db.commit()
    finally:
        db.close()


@celery_app.task(name="handle_lead_with_ai_task")
def handle_lead_with_ai_task(tenant_id: str, lead_id: str):
    from app.services.verticals.sales import SalesService
    from app.models.verticals import Lead
    from datetime import datetime

    # 1. Run enrichment
    enrich_lead_task(tenant_id, lead_id)

    # 2. Run scoring & outreach generation
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id).first()
        if lead:
            service = SalesService(db, tenant_id)
            async_to_sync(service.score_lead)(lead_id)
            
            message = async_to_sync(service.generate_outreach)(lead_id)
            if message:
                lead.status = "contacted"
                conv = list((lead.data or {}).get("conversation") or [])
                conv.append({
                    "direction": "outbound",
                    "channel": "smtp",
                    "content": message,
                    "subject": f"Partnership Opportunity - {lead.company}",
                    "at": datetime.utcnow().isoformat()
                })
                lead.data = {
                    **(lead.data or {}),
                    "outreach_channel": "smtp",
                    "outbound_subject": f"Partnership Opportunity - {lead.company}",
                    "outbound_body": message,
                    "outreach_sent_at": datetime.utcnow().isoformat(),
                    "conversation": conv
                }
                db.commit()
    finally:
        db.close()


@celery_app.task(name="generate_campaign_task")
def generate_campaign_task(tenant_id: str, params: dict):
    from app.services.llm_gateway import LLMGateway
    from app.models.verticals import ContentPost
    from app.models.agents import ActivityLog
    from app.services.marketing.campaign_os.orchestrator import CampaignOSOrchestrator
    from asgiref.sync import async_to_sync
    import logging
    
    task_logger = logging.getLogger("generate_campaign_task")
    db = SessionLocal()
    try:
        topic = params.get("topic", "our company")
        days = int(params.get("days", 30))
        platforms = params.get("platforms", ["linkedin", "instagram", "facebook"])
        image_provider = params.get("image_provider", "openai")
        video_provider = params.get("video_provider", "pika")
        generate_images = bool(params.get("generate_images", True))
        generate_videos = bool(params.get("generate_videos", False))

        # Log start activity
        log = ActivityLog(
            tenant_id=tenant_id,
            agent_name="Campaign OS",
            action="Campaign DAG Started",
            description=f"Initiating 3-stage Campaign OS DAG for a {days}-day multi-platform campaign on: {topic}.",
            status="pending"
        )
        db.add(log)
        db.commit()

        # Execute the 3-stage Campaign OS Orchestrator
        orchestrator = CampaignOSOrchestrator(db, tenant_id)
        result = async_to_sync(orchestrator.execute_campaign_dag)(params)

        # Dispatch Media Rendering with Circuit Breakers (if requested and prompt exists)
        llm = LLMGateway(db, tenant_id)
        created_posts = (
            db.query(ContentPost)
            .filter(
                ContentPost.tenant_id == tenant_id,
                ContentPost.image_url == None,  # noqa: E711
            )
            .order_by(ContentPost.created_at.desc())
            .limit(days * len(platforms))
            .all()
        )

        for post in created_posts:
            # Image Rendering Dispatch
            if generate_images and post.image_prompt and not post.image_url:
                try:
                    raw = async_to_sync(llm.generate_image)(post.image_prompt, provider=image_provider)
                    if raw and not raw.startswith("error:"):
                        post.image_url = async_to_sync(ensure_public_url)(raw, prefix="img")
                    elif raw and raw.startswith("error:"):
                        post.image_url = raw  # Keep error sentinel for UI warning
                except Exception as img_err:
                    task_logger.warning(f"Image generation failed gracefully for post {post.id}: {img_err}")
                    # Circuit breaker: graceful degradation to text-only

            # Video Rendering Dispatch
            if generate_videos and post.video_prompt and not post.video_url:
                try:
                    v_raw = async_to_sync(llm.generate_video)(post.video_prompt, provider=video_provider)
                    if v_raw and not str(v_raw).startswith("error:"):
                        post.video_url = async_to_sync(ensure_public_url)(v_raw, prefix="vid", default_mime="video/mp4")
                except Exception as vid_err:
                    task_logger.warning(f"Video generation failed gracefully for post {post.id}: {vid_err}")

        db.commit()

        final_log = ActivityLog(
            tenant_id=tenant_id,
            agent_name="Campaign OS",
            action="Campaign DAG Completed",
            description=f"Generated {result.get('total_posts_generated', 0)} posts. Auto-approved: {result.get('approved_count', 0)}, Review needed: {result.get('needs_review_count', 0)}.",
            status="success"
        )
        db.add(final_log)
        db.commit()

        return result

    except Exception as e:
        task_logger.error(f"Error in Campaign OS DAG task: {e}", exc_info=True)
        error_log = ActivityLog(
            tenant_id=tenant_id,
            agent_name="Campaign OS",
            action="Campaign DAG Failed",
            description=f"Error in Campaign OS DAG: {str(e)[:300]}",
            status="failed"
        )
        db.add(error_log)
        db.commit()
        raise e
    finally:
        db.close()


@celery_app.task(name="publish_post_by_id")
def publish_post_by_id(post_id: str):
    from app.models.verticals import ContentPost
    from app.services.social.publish_helpers import publish_post_sync

    db = SessionLocal()
    try:
        post = db.query(ContentPost).filter(ContentPost.id == post_id).first()
        if post:
            publish_post_sync(db, post)
    finally:
        db.close()


@celery_app.task(name="publish_scheduled_posts")
def publish_scheduled_posts():
    from app.models.verticals import ContentPost
    from datetime import datetime, timezone
    from app.services.social.publish_helpers import publish_post_sync

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        posts = (
            db.query(ContentPost)
            .filter(
                ContentPost.approval_status == "approved",
                ContentPost.scheduled_at <= now,
                ContentPost.status != "published",
            )
            .all()
        )

        for post in posts:
            publish_post_sync(db, post)
    finally:
        db.close()

@celery_app.task(name="run_daily_operations")
def run_daily_operations():
    from app.models.base import Tenant
    from app.services.agents.orchestrator import OrchestratorAgent
    db = SessionLocal()
    try:
        # First, run daily ops routines
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        for t in tenants:
            agent = OrchestratorAgent(db, t.id)
            async_to_sync(agent.run_daily_ops)()
            
        # Also run scheduled post publishing
        publish_scheduled_posts()
    finally:
        db.close()

@celery_app.task(name="auto_reply_task")
def auto_reply_task(tenant_id: str, ticket_id: str, trigger_msg_id: str, channel: str):
    from app.services.agents.support import SupportAgent
    db = SessionLocal()
    try:
        agent = SupportAgent(db, tenant_id)
        async_to_sync(agent.process_auto_reply)(ticket_id, trigger_msg_id, channel)
    except Exception as e:
        print(f"Error in auto_reply_task: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="run_boardroom_meeting_task")
def run_boardroom_meeting_task(
    tenant_id: str,
    meeting_id: str,
    provider: Optional[str] = None,
    model: Optional[str] = None
):
    from app.services.agents.boardroom import BoardroomService
    db = SessionLocal()
    try:
        service = BoardroomService(db, tenant_id, provider=provider, model=model)
        async_to_sync(service.run_meeting)(meeting_id)
    except Exception as e:
        print(f"Error in run_boardroom_meeting_task: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="check_ticket_coordination_task")
def check_ticket_coordination_task(tenant_id: str, ticket_id: str):
    from app.services.agents.boardroom import BoardroomService
    db = SessionLocal()
    try:
        service = BoardroomService(db, tenant_id)
        classification = async_to_sync(service.classify_ticket_inquiry)(ticket_id)
        if classification.get("needs_meeting"):
            async_to_sync(service.create_meeting_from_ticket)(ticket_id, classification)
    except Exception as e:
        print(f"Error in check_ticket_coordination_task: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="execute_local_batch_task")
def execute_local_batch_task(batch_id: str):
    from app.models.base import AIBatchJob
    from app.services.ai_gateway import ai_gateway
    from datetime import datetime, timezone
    
    db = SessionLocal()
    try:
        job = db.query(AIBatchJob).filter(AIBatchJob.id == batch_id).first()
        if not job:
            print(f"Batch job {batch_id} not found.")
            return

        tasks = job.results.get("tasks", [])
        completed_results = []
        completed_count = 0
        failed_count = 0
        
        for index, t in enumerate(tasks):
            custom_id = f"task-{index}"
            try:
                content = async_to_sync(ai_gateway.executeRequest)(
                    db=db,
                    tenant_id=job.tenant_id,
                    prompt=t.get("prompt"),
                    model=job.model,
                    provider=job.provider,
                    system_prompt=t.get("system_prompt"),
                    task_type="bulk_batch",
                    bulk=True,
                    **(t.get("kwargs") or {})
                )
                completed_results.append({
                    "custom_id": custom_id,
                    "content": content,
                    "status": "success",
                    "input_tokens": len(t.get("prompt", "").split()) + len(t.get("system_prompt", "").split() if t.get("system_prompt") else []),
                    "output_tokens": len(content.split())
                })
                completed_count += 1
            except Exception as e:
                print(f"Error executing batch task {custom_id}: {e}")
                completed_results.append({
                    "custom_id": custom_id,
                    "content": "",
                    "status": "failed",
                    "error": str(e),
                    "input_tokens": 0,
                    "output_tokens": 0
                })
                failed_count += 1
            
            # Save progress incrementally
            job.completed_tasks = completed_count
            job.failed_tasks = failed_count
            job.results = {"completed": completed_results, "tasks": tasks}
            db.commit()

        job.status = "completed" if completed_count > 0 else "failed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as ex:
        print(f"Failed executing batch {batch_id}: {ex}")
        job = db.query(AIBatchJob).filter(AIBatchJob.id == batch_id).first()
        if job:
            job.status = "failed"
            db.commit()
    finally:
        db.close()

@celery_app.task(name="poll_native_batches_task")
def poll_native_batches_task():
    from app.models.base import AIBatchJob
    from app.services.ai_gateway import ai_gateway
    from app.services.ai_gateway.batching import BatchExecutionEngine
    
    db = SessionLocal()
    try:
        active_native_jobs = db.query(AIBatchJob).filter(
            AIBatchJob.status == "processing",
            AIBatchJob.provider_batch_id != None
        ).all()
        
        for job in active_native_jobs:
            api_key = ai_gateway._get_api_key(db, job.tenant_id, job.provider)
            adapter = ai_gateway._get_adapter(job.provider, api_key)
            async_to_sync(BatchExecutionEngine.monitorBatch)(db, job.id, adapter)
    except Exception as e:
        print(f"Error polling native batches: {e}")
    finally:
        db.close()

@celery_app.task(name="process_sales_inbound_task")
def process_sales_inbound_task(
    tenant_id: str,
    lead_id: str,
    channel: str,
    content: str,
    subject: str = None,
    external_id: str = None,
):
    from app.services.sales.reply_handler import SalesReplyHandler

    db = SessionLocal()
    try:
        handler = SalesReplyHandler(db, tenant_id)
        async_to_sync(handler.process_inbound)(
            lead_id, channel, content, subject=subject, external_id=external_id
        )
    except Exception as e:
        print(f"process_sales_inbound_task error: {e}")
        raise
    finally:
        db.close()


@celery_app.task(name="sales_auto_reply_task")
def sales_auto_reply_task(
    tenant_id: str,
    lead_id: str,
    channel: str,
    reply_content: str,
    trigger_external_id: str,
):
    from app.models.verticals import Lead
    from app.services.sales.reply_handler import SalesReplyHandler

    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id).first()
        if not lead:
            return
        data = lead.data or {}
        if trigger_external_id and data.get("pending_auto_reply_for") != trigger_external_id:
            return

        handler = SalesReplyHandler(db, tenant_id)
        async_to_sync(handler.send_sales_reply)(lead, channel, reply_content)
    except Exception as e:
        print(f"sales_auto_reply_task error: {e}")
    finally:
        db.close()


@celery_app.task(name="poll_gmail_sales_inbox")
def poll_gmail_sales_inbox():
    from app.models.base import Tenant
    from app.services.sales.gmail_poll import poll_gmail_inbox_for_sales

    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        for tenant in tenants:
            try:
                poll_gmail_inbox_for_sales(db, tenant.id)
            except Exception as e:
                print(f"Gmail poll error for {tenant.id}: {e}")
    finally:
        db.close()


@celery_app.task(name="send_sales_meeting_reminders")
def send_sales_meeting_reminders():
    """Telegram: 24h-before meeting, 1h-before call, 24h follow-up on contacted leads."""
    from datetime import datetime, timedelta, timezone
    from app.models.base import Tenant
    from app.models.verticals import Lead
    from app.services.notifications.sales_alerts import (
        format_followup_reminder,
        format_meeting_reminder_1h,
        format_meeting_reminder_tomorrow,
        meeting_start_from_lead,
        send_sales_telegram,
    )

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()

        for tenant in tenants:
            # Meeting reminders
            scheduled = (
                db.query(Lead)
                .filter(
                    Lead.tenant_id == tenant.id,
                    Lead.status == "meeting_scheduled",
                )
                .all()
            )
            for lead in scheduled:
                data = dict(lead.data or {})
                starts_at = meeting_start_from_lead(lead)
                if not starts_at:
                    continue

                delta = starts_at - now
                meeting_time = data.get("meeting_time", starts_at.isoformat())
                meet_url = data.get("meeting_link", "")

                # ~24 hours before
                if (
                    timedelta(hours=23, minutes=30) <= delta <= timedelta(hours=24, minutes=30)
                    and not data.get("reminder_24h_sent")
                ):
                    msg = format_meeting_reminder_tomorrow(lead, meeting_time, meet_url)
                    if send_sales_telegram(db, tenant.id, msg):
                        data["reminder_24h_sent"] = True
                        lead.data = data
                        db.commit()

                # ~1 hour before
                if (
                    timedelta(minutes=50) <= delta <= timedelta(hours=1, minutes=10)
                    and not data.get("reminder_1h_sent")
                ):
                    msg = format_meeting_reminder_1h(lead, meeting_time, meet_url)
                    if send_sales_telegram(db, tenant.id, msg):
                        data["reminder_1h_sent"] = True
                        lead.data = data
                        db.commit()

            # Follow-up: contacted 24h+ ago, no meeting
            contacted = (
                db.query(Lead)
                .filter(
                    Lead.tenant_id == tenant.id,
                    Lead.status == "contacted",
                )
                .all()
            )
            for lead in contacted:
                data = dict(lead.data or {})
                if data.get("followup_reminder_sent"):
                    continue
                raw_sent = data.get("outreach_sent_at")
                if not raw_sent:
                    continue
                try:
                    sent_at = datetime.fromisoformat(str(raw_sent).replace("Z", "+00:00"))
                    if sent_at.tzinfo is None:
                        sent_at = sent_at.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    continue

                if now - sent_at >= timedelta(hours=24):
                    msg = format_followup_reminder(lead)
                    if send_sales_telegram(db, tenant.id, msg):
                        data["followup_reminder_sent"] = True
                        lead.data = data
                        db.commit()
    except Exception as e:
        print(f"Error in send_sales_meeting_reminders: {e}")
    finally:
        db.close()


@celery_app.task(name="poll_and_execute_workflows")
def poll_and_execute_workflows():
    from app.models.workflows import WorkflowTask
    from app.services.agents.workflow_engine import WorkflowEngine
    from datetime import datetime, timezone
    
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        tasks_to_run = db.query(WorkflowTask).filter(
            WorkflowTask.status == "pending",
            WorkflowTask.scheduled_at <= now
        ).all()
        
        if tasks_to_run:
            engine = WorkflowEngine(db)
            for task in tasks_to_run:
                async_to_sync(engine.execute_task)(task)
                
    except Exception as e:
        print(f"Error polling workflows: {e}")
    finally:
        db.close()


@celery_app.task(name="run_ceo_workflow_task")
def run_ceo_workflow_task(tenant_id: str, workflow_id: str):
    from app.services.agents.ceo import CEOService
    db = SessionLocal()
    try:
        service = CEOService(db, tenant_id)
        async_to_sync(service.execute_workflow)(workflow_id)
    except Exception as e:
        print(f"Error in run_ceo_workflow_task: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="run_sales_v3_task")
def run_sales_v3_task(tenant_id: str, provider: str = "gemini", model: str = None, count: int = 50):
    from app.services.agents.sales import SalesAgent
    db = SessionLocal()
    try:
        agent = SalesAgent(db, tenant_id)
        async_to_sync(agent.run_sales_ai_v3_workflow)(provider=provider, model=model, count=count)
    except Exception as e:
        print(f"Error in run_sales_v3_task: {e}")
        raise e
    finally:
        db.close()


@celery_app.task(name="sync_marketing_insights_task")
def sync_marketing_insights_task(tenant_id: str = None, limit: int = 50):
    """Pull FB/IG/LinkedIn insights and rebuild learning patterns."""
    from app.models.base import Tenant
    from app.services.marketing.analytics import MarketingAnalyticsService

    db = SessionLocal()
    try:
        if tenant_id:
            tenant_ids = [tenant_id]
        else:
            tenant_ids = [t.id for t in db.query(Tenant).filter(Tenant.is_active == True).all()]  # noqa: E712

        summary = []
        for tid in tenant_ids:
            try:
                result = async_to_sync(MarketingAnalyticsService(db, tid).sync_all)(limit=limit)
                summary.append({"tenant_id": tid, **{k: result.get(k) for k in ("synced", "errors", "patterns_updated")}})
            except Exception as e:
                summary.append({"tenant_id": tid, "error": str(e)[:200]})
        return {"status": "ok", "tenants": summary}
    finally:
        db.close()


@celery_app.task(name="rebuild_marketing_learning_task")
def rebuild_marketing_learning_task(tenant_id: str):
    from app.services.marketing.analytics import MarketingAnalyticsService
    db = SessionLocal()
    try:
        n = MarketingAnalyticsService(db, tenant_id).rebuild_learning_patterns()
        return {"status": "ok", "patterns_updated": n}
    finally:
        db.close()


@celery_app.task(name="dead_letter_handler")
def dead_letter_handler(task_name: str, task_id: str, exception: str, args: str, kwargs: str):
    import logging
    import ast
    from app.db.session import SessionLocal
    from app.services.durable_workflows import DeadLetterService

    logger = logging.getLogger(__name__)
    logger.error(
        f"[DLQ EVENT] Celery task '{task_name}' (ID: {task_id}) failed. "
        f"Exception: {exception}. Args: {args}, Kwargs: {kwargs}"
    )
    db = SessionLocal()
    try:
        parsed_args = []
        parsed_kwargs = {}
        try:
            parsed_args = list(ast.literal_eval(args)) if args else []
        except Exception:
            parsed_args = [args]
        try:
            parsed_kwargs = dict(ast.literal_eval(kwargs)) if kwargs else {}
        except Exception:
            parsed_kwargs = {"raw": kwargs}
        tenant_id = None
        if parsed_args and isinstance(parsed_args[0], str):
            tenant_id = parsed_args[0]
        elif isinstance(parsed_kwargs, dict):
            tenant_id = parsed_kwargs.get("tenant_id")
        DeadLetterService(db).record(
            task_name=task_name,
            task_id=task_id,
            args=parsed_args,
            kwargs=parsed_kwargs,
            error=exception,
            tenant_id=tenant_id,
        )
        return {"status": "DLQ_RECORDED", "task_id": task_id, "persisted": True}
    except Exception as e:
        logger.error(f"Failed to persist DLQ job: {e}")
        return {"status": "DLQ_RECORDED", "task_id": task_id, "persisted": False}
    finally:
        db.close()



@celery_app.task(name="plan_video_task")
def plan_video_task(tenant_id: str, project_id: str):
    from app.services.agents.video import VideoAgent
    from app.db.session import SessionLocal
    from asgiref.sync import async_to_sync
    
    db = SessionLocal()
    try:
        agent = VideoAgent(db, tenant_id)
        async_to_sync(agent.plan_video)(project_id)
    except Exception as e:
        import logging
        logging.error(f"Error in plan_video_task: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="render_video_task")
def render_video_task(tenant_id: str, project_id: str):
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        import httpx
        import logging
        from app.models.video import VideoProject, VideoRender
        from app.services.media.storage import upload_file_to_storage
        import os
        from datetime import datetime, timezone
        from asgiref.sync import async_to_sync

        project = db.query(VideoProject).filter(
            VideoProject.id == project_id, 
            VideoProject.tenant_id == tenant_id
        ).first()

        if not project or not project.blueprint:
            logging.error(f"Cannot render video: Project {project_id} not found or has no blueprint.")
            return

        project.status = "rendering"
        render_job = VideoRender(project_id=project.id, status="processing")
        db.add(render_job)
        db.commit()

        # Call local Node.js renderer service
        with httpx.Client(timeout=1200.0) as client:
            resp = client.post(
                "http://localhost:8002/render",
                json=project.blueprint
            )
            
            if resp.status_code == 200:
                data = resp.json()
                local_file = data.get("file")
                
                if local_file and os.path.exists(local_file):
                    # Upload local mp4 file to public storage
                    with open(local_file, "rb") as f:
                        file_bytes = f.read()
                    
                    filename = f"render_{project_id}_{int(datetime.now(timezone.utc).timestamp())}.mp4"
                    public_url = async_to_sync(upload_file_to_storage)(file_bytes, filename, "video/mp4")
                    
                    project.final_video_url = public_url
                    project.status = "completed"
                    render_job.status = "success"
                    render_job.render_url = public_url
                    render_job.progress = 100.0
                    render_job.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    # Cleanup local file
                    try:
                        os.remove(local_file)
                    except:
                        pass
                else:
                    raise Exception("Renderer returned success but file not found on disk.")
            else:
                raise Exception(f"Renderer API failed with status {resp.status_code}: {resp.text}")

    except Exception as e:
        logging.error(f"Video rendering failed for project {project_id}: {e}")
        try:
            if 'render_job' in locals():
                render_job.status = "error"
                render_job.error_logs = str(e)
            if 'project' in locals():
                project.status = "failed"
            db.commit()
        except Exception as inner_e:
            logging.error(f"Failed to update error status in DB: {inner_e}")
            db.rollback()
    finally:
        db.close()


@celery_app.task(name="recrawl_due_knowledge_sources_task")
def recrawl_due_knowledge_sources_task():
    """Periodically check and re-crawl scheduled knowledge sources."""
    from datetime import datetime, timezone, timedelta
    from app.models.agents import KnowledgeSource
    from app.services.web_ingestion.website_sync import WebsiteSyncService

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        sources = db.query(KnowledgeSource).filter(
            KnowledgeSource.schedule.in_(["daily", "weekly"]),
            KnowledgeSource.last_status != "running",
        ).all()

        for s in sources:
            should_crawl = False
            if not s.last_crawled_at:
                should_crawl = True
            elif s.schedule == "daily" and (now - s.last_crawled_at) > timedelta(days=1):
                should_crawl = True
            elif s.schedule == "weekly" and (now - s.last_crawled_at) > timedelta(days=7):
                should_crawl = True

            if should_crawl:
                try:
                    sync_service = WebsiteSyncService(db, s.tenant_id)
                    async_to_sync(sync_service.sync_knowledge_source)(s.id)
                except Exception as e:
                    logging.error(f"Periodic crawl failed for source {s.id}: {e}")
    finally:
        db.close()
