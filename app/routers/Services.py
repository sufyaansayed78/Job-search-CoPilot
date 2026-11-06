
from http.client import HTTPException

from app.auth import get_current_user
from app.database import get_db
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select
from app.models import GmailCredential, SyncJob
from sqlalchemy.orm import Session
from app.services.gmail import fernet 

router = APIRouter(prefix="/services", tags=["services"])

@router.post("/gmail/sync", status_code=202)
def start_sync(user=Depends(get_current_user), db: Session = Depends(get_db)):
    cred = db.get(GmailCredential, user.id)
    if not cred:
        raise HTTPException(400, "Gmail not connected. Please connect your Gmail account first.")
    lock_key = f"gmail_sync_lock:{user.id}"
    if not r.set(lock_key, "1", nx=True, ex=600):   # atomic "set if not exists"
        raise HTTPException(409, "Sync already in progress")
    job = SyncJob(user_id=user.id)
    db.add(job); db.commit()
    gmail_sync_task.delay(str(job.id))
    return {"job_id": str(job.id)}


@router.get("/gmail/sync/{job_id}")
def sync_status(job_id: uuid.UUID, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    job = db.get(SyncJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404)
    return {"status": job.status, "emails_checked": job.emails_checked,
            "updates_applied": job.updates_applied,
            "suggestions_created": job.suggestions_created, "error": job.error}