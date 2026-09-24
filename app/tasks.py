import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def analyze_job_posting_task(self, job_posting_id: str):
    """Async task: run the LangGraph gap-analysis agent for one job posting
    and persist the result. Retries on transient failures (e.g. LLM API
    hiccups) rather than silently dropping the analysis."""
    from app.database import SessionLocal
    from app.models import JobPosting, GapAnalysis, User
    from app.agent.gap_analysis import run_gap_analysis

    db = SessionLocal()
    try:
        posting = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
        if posting is None:
            logger.error(f"Job posting {job_posting_id} not found.")
            return

        posting.analysis_status = "pending"
        db.commit()

        user = db.query(User).filter(User.id == posting.user_id).first()
        result = run_gap_analysis(
            job_description=posting.raw_description,
            resume_text=user.resume_text or "",
        )

        analysis = GapAnalysis(job_posting_id=posting.id, **result)
        db.add(analysis)
        posting.analysis_status = "done"
        db.commit()

        logger.info(
            f"Analysis complete for {job_posting_id}: "
            f"score={result['match_score']}, rec={result['recommendation']}"
        )
        return result

    except Exception as exc:
        db.rollback()
        logger.error(f"Analysis failed for {job_posting_id}: {exc}")
        try:
            posting = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
            if posting:
                posting.analysis_status = "failed"
                db.commit()
        except Exception:
            db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
