from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.celery_app import celery_app
from app.core.config import get_settings
from app.core.logging import bind_log_context, reset_log_context
from app.core.metrics import record_task_execution
from app.db.session import SessionLocal
from app.events.schemas import ApplicationReceivedEvent
from app.repositories.event_processing_repo import EventProcessingRepository
from app.tasks import APPLICATION_SCORING_TASK, build_application_service, normalize_skills, run_async_task

settings = get_settings()


@celery_app.task(
    autoretry_for=(Exception,),
    bind=True,
    max_retries=settings.celery_task_max_retries,
    name=APPLICATION_SCORING_TASK,
    retry_backoff=settings.celery_task_retry_backoff,
    retry_jitter=False,
)
def process_application_scoring(
    self,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    return run_async_task(
        _process_application_scoring(
            payload=payload,
            headers=headers,
            celery_task_id=self.request.id,
        )
    )


async def _process_application_scoring(
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    celery_task_id: str | None,
) -> dict[str, Any]:
    event = ApplicationReceivedEvent.model_validate(payload)
    tokens = bind_log_context(
        user_id=headers.get("user_id"),
        workflow_id=headers.get("workflow_id"),
        correlation_id=headers.get("correlation_id"),
    )

    try:
        async with SessionLocal() as session:
            processing_repo = EventProcessingRepository(session)
            record, claimed = await processing_repo.claim_for_processing(
                event_id=event.event_id,
                handler_name=APPLICATION_SCORING_TASK,
            )
            if record is None:
                await processing_repo.get_or_create(
                    event_id=event.event_id,
                    handler_name=APPLICATION_SCORING_TASK,
                    event_type=event.event_type(),
                    topic_name=event.topic_name(),
                    aggregate_id=event.aggregate_id,
                    schema_version=event.schema_version,
                    metadata={"celery_task_id": celery_task_id},
                )
                record, claimed = await processing_repo.claim_for_processing(
                    event_id=event.event_id,
                    handler_name=APPLICATION_SCORING_TASK,
                )

            if record is None or not claimed:
                record_task_execution(task_name=APPLICATION_SCORING_TASK, status="skipped")
                await session.commit()
                return {"application_id": str(event.application_id), "status": "skipped"}

            try:
                application_service = build_application_service(session)
                context = await application_service.get_background_task_context(event.application_id)
                resume_parsing = dict(context["application_metadata"].get("resume_parsing", {}))

                if resume_parsing.get("status") != "parsed":
                    pending_result = {
                        "status": "pending_resume",
                        "reason": "Waiting for parsed resume data before scoring",
                    }
                    await application_service.record_scoring_result(
                        event.application_id,
                        scoring_result=pending_result,
                    )
                    await processing_repo.mark_completed(
                        record,
                        metadata={
                            "celery_task_id": celery_task_id,
                            "event_type": event.event_type(),
                            "headers": headers,
                            "status": "pending_resume",
                        },
                    )
                    record_task_execution(task_name=APPLICATION_SCORING_TASK, status="pending_resume")
                    await session.commit()
                    return {
                        "application_id": str(event.application_id),
                        "status": "pending_resume",
                    }

                eligibility_result = dict(context["eligibility_result"])
                required_skills = normalize_skills(context["job_required_skills"])
                master_profile = dict(context["candidate_master_profile"])
                resume_structured_data = context["resume_structured_data"]
                master_profile_skills = normalize_skills(master_profile.get("skills", []))
                resume_skills = normalize_skills(
                    resume_structured_data.get("skills", []) if isinstance(resume_structured_data, dict) else []
                )
                candidate_skill_pool = master_profile_skills | resume_skills
                matched_skills = sorted(candidate_skill_pool & required_skills)
                missing_skills = sorted(required_skills - candidate_skill_pool)
                observed_match_score = 1.0 if not required_skills else len(matched_skills) / len(required_skills)
                eligibility_match_score = float(eligibility_result.get("match_score") or 0.0)
                final_score = round(((eligibility_match_score * 0.6) + (observed_match_score * 0.4)), 4)

                scoring_result = {
                    "status": "completed",
                    "event_id": str(event.event_id),
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "score": final_score,
                    "matched_skills": matched_skills,
                    "missing_skills": missing_skills,
                    "inputs": {
                        "eligibility_match_score": eligibility_match_score,
                        "observed_match_score": round(observed_match_score, 4),
                        "required_skill_count": len(required_skills),
                        "master_profile_skill_count": len(master_profile_skills),
                        "resume_skill_count": len(resume_skills),
                        "resume_data_available": resume_structured_data is not None,
                    },
                }

                await application_service.record_scoring_result(
                    event.application_id,
                    scoring_result=scoring_result,
                )
                await processing_repo.mark_completed(
                    record,
                    metadata={
                        "celery_task_id": celery_task_id,
                        "event_type": event.event_type(),
                        "headers": headers,
                        "score": final_score,
                    },
                )
                record_task_execution(task_name=APPLICATION_SCORING_TASK, status="success")
                await session.commit()
                return {
                    "application_id": str(event.application_id),
                    "event_id": str(event.event_id),
                    "score": final_score,
                }
            except Exception as exc:
                await processing_repo.mark_failed(
                    record,
                    error_message=str(exc),
                    metadata={
                        "celery_task_id": celery_task_id,
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                record_task_execution(task_name=APPLICATION_SCORING_TASK, status="failure")
                await session.commit()
                raise
    finally:
        reset_log_context(tokens)
