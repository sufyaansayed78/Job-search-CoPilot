import logging
import uuid
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from app.services_imp.gmail import  mark_job_failed
from app.Services import run_gmail_sync
from app.celery_app import celery_app
logger = logging.getLogger(__name__)
from googleapiclient.errors import HttpError
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

@celery_app.task(
    bind=True,
    autoretry_for=(HttpError, ConnectionError),
    retry_backoff=True,          # 1s, 2s, 4s, ...
    retry_backoff_max=60,
    max_retries=3,
)
def analyze_job_posting_task(self, job_posting_id: str):
    """Async task: run the LangGraph gap-analysis agent for one job posting
    and persist the result. Retries on transient failures (e.g. LLM API
    hiccups) rather than silently dropping the analysis."""
    from app.database import SessionLocal
    from app.models import JobPosting, GapAnalysis, User
    from app.agent.gap_analysis import run_gap_analysis
    logging.info(f"In the analyze_job_posting_task function ")
    db = SessionLocal()
    try:
        posting = db.query(JobPosting).filter(JobPosting.id == job_posting_id).first()
        if posting is None:
            logging.info("Job_Posting not found")
            logger.error(f"Job posting {job_posting_id} not found.")
            return

        posting.analysis_status = "pending"
        db.commit()

        user = db.query(User).filter(User.id == posting.user_id).first()
        logging.info("Calling the run gap analysis function")

        result = run_gap_analysis(
            job_description=posting.raw_description,
            resume_text=user.resume_text or "",
        )
        logging.info(f"Got this result from the gap_analysis_function{result}")

        analysis = GapAnalysis(job_posting_id=posting.id, **result)
        db.add(analysis)
        posting.analysis_status = "done"
        db.commit()

        logging.info(
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


@celery_app.task(
    bind=True,
    autoretry_for=(HttpError, ConnectionError),
    retry_backoff=True,          # 1s, 2s, 4s, ...
    retry_backoff_max=60,
    max_retries=3,
)
def gmail_sync_task(self, job_id: uuid.UUID):
    try:
        run_gmail_sync(job_id)
    except SoftTimeLimitExceeded:
        mark_job_failed(job_id, "Sync took too long, try again")
        