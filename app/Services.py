
from datetime import datetime, timedelta
import logging
from typing import Annotated
import uuid

from app.database import SessionLocal
from app.models import GmailCredential, SyncJob 
#from app.auth import get_current_user
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from google.auth.exceptions import RefreshError
from app.services_imp.gmail import build_gmail_service, fetch_job_emails, process_email


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)



def run_gmail_sync(job_id: uuid.UUID):
    logging.info(f"Starting Gmail sync for job {job_id}")
    with SessionLocal() as db:          # own session, not the request's
        logging.info(f"Fetching SyncJob {job_id} from database")
        job = db.get(SyncJob, job_id)
        logging.info(f"Fetched SyncJob: {job}")
        job.status = "running"; db.commit()
        try:
            logging.info(f"Fetching GmailCredential for user {job.user_id}")
            cred = db.get(GmailCredential, job.user_id)
            logging.info(f"Fetched GmailCredential: {cred}")
            logging.info(f"Building Gmail service for user {job.user_id}")
            service = build_gmail_service(cred)
            logging.info(f"Gmail service built successfully for user {job.user_id}")
            since = cred.last_synced_at or datetime.utcnow() - timedelta(days=10)
            logging.info(f"Fetching job emails since {since} for user {job.user_id}")
            for msg in fetch_job_emails(service, since):
                logging.info(f"Processing message ID: {msg['id']} for user {job.user_id}")
                process_email(db, job, msg)  # match → classify → update/suggest
                job.emails_checked += 1; db.commit()
            logging.info(f"Finished processing emails for job {job_id}. Updating last_synced_at.")
            cred.last_synced_at = datetime.utcnow()
            job.status = "done"
        except RefreshError:
            job.status, job.error = "failed", "Gmail access expired, please reconnect"
        except Exception as e:
            job.status, job.error = "failed", str(e)
        db.commit()









