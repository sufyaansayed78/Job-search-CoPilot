
from datetime import datetime, timedelta
from typing import Annotated
import uuid

from app.database import SessionLocal
from app.models import GmailCredential, SyncJob 
from app.auth import get_current_user
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from google.auth.exceptions import RefreshError
from app.services_imp.gmail import build_gmail_service, fetch_job_emails, process_email




def run_gmail_sync(job_id: uuid.UUID):
    with SessionLocal() as db:          # own session, not the request's
        job = db.get(SyncJob, job_id)
        job.status = "running"; db.commit()
        try:
            cred = db.get(GmailCredential, job.user_id)
            service = build_gmail_service(cred)
            since = cred.last_synced_at or datetime.utcnow() - timedelta(days=60)
            for msg in fetch_job_emails(service, since):
                process_email(db, job, msg)  # match → classify → update/suggest
                job.emails_checked += 1; db.commit()
            cred.last_synced_at = datetime.utcnow()
            job.status = "done"
        except RefreshError:
            job.status, job.error = "failed", "Gmail access expired, please reconnect"
        except Exception as e:
            job.status, job.error = "failed", str(e)
        db.commit()









