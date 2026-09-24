import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Application, JobPosting, User, ApplicationStatus
from app.schemas import ApplicationCreate, ApplicationOut, ApplicationStatusUpdate
from app.auth import get_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


def _get_owned_application(app_id: uuid.UUID, current_user: User, db: Session) -> Application:
    application = db.query(Application).filter(
        Application.id == app_id, Application.user_id == current_user.id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")
    return application


@router.get("/", response_model=list[ApplicationOut])
def list_applications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.updated_at.desc())
        .all()
    )


@router.post("/", response_model=ApplicationOut, status_code=201)
def create_application(
    payload: ApplicationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    posting = db.query(JobPosting).filter(
        JobPosting.id == payload.job_posting_id, JobPosting.user_id == current_user.id
    ).first()
    if not posting:
        raise HTTPException(status_code=400, detail="Job posting not found for this user.")

    application = Application(**payload.model_dump(), user_id=current_user.id)
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.patch("/{app_id}/status", response_model=ApplicationOut)
def update_status(
    app_id: uuid.UUID,
    payload: ApplicationStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    application = _get_owned_application(app_id, current_user, db)
    application.status = payload.status
    if payload.status == ApplicationStatus.APPLIED and application.applied_date is None:
        application.applied_date = datetime.now(timezone.utc)
    if payload.follow_up_date is not None:
        application.follow_up_date = payload.follow_up_date
    if payload.notes is not None:
        application.notes = payload.notes
    db.commit()
    db.refresh(application)
    return application


@router.get("/upcoming-follow-ups", response_model=list[ApplicationOut])
def upcoming_follow_ups(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    within_days: int = 7,
):
    """The actual point of tracking follow-up dates: surfacing the ones
    that are coming up, instead of relying on remembering them."""
    cutoff = datetime.now(timezone.utc) + timedelta(days=within_days)
    return (
        db.query(Application)
        .filter(
            Application.user_id == current_user.id,
            Application.follow_up_date.isnot(None),
            Application.follow_up_date <= cutoff,
        )
        .order_by(Application.follow_up_date.asc())
        .all()
    )
