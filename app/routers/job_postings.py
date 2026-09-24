import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobPosting, Company, User
from app.schemas import JobPostingCreate, JobPostingOut, GapAnalysisOut
from app.auth import get_current_user
from app.tasks import analyze_job_posting_task

router = APIRouter(prefix="/job-postings", tags=["job-postings"])


def _get_owned_posting(posting_id: uuid.UUID, current_user: User, db: Session) -> JobPosting:
    posting = db.query(JobPosting).filter(
        JobPosting.id == posting_id, JobPosting.user_id == current_user.id
    ).first()
    if not posting:
        raise HTTPException(status_code=404, detail="Job posting not found.")
    return posting


@router.get("/", response_model=list[JobPostingOut])
def list_postings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return (
        db.query(JobPosting)
        .filter(JobPosting.user_id == current_user.id)
        .order_by(JobPosting.created_at.desc())
        .all()
    )


@router.post("/", response_model=JobPostingOut, status_code=201)
def create_posting(
    payload: JobPostingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(
        Company.id == payload.company_id, Company.user_id == current_user.id
    ).first()
    if not company:
        raise HTTPException(status_code=400, detail="Company not found for this user.")

    posting = JobPosting(**payload.model_dump(), user_id=current_user.id)
    db.add(posting)
    db.commit()
    db.refresh(posting)
    return posting


@router.get("/{posting_id}", response_model=JobPostingOut)
def get_posting(
    posting_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return _get_owned_posting(posting_id, current_user, db)


@router.post("/{posting_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
def trigger_analysis(
    posting_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """Kicks off the LangGraph agent asynchronously. The LLM call takes a
    few seconds — too slow to hold the HTTP connection open for, so this
    returns immediately and the client polls GET /analysis."""
    posting = _get_owned_posting(posting_id, current_user, db)
    posting.analysis_status = "pending"
    db.commit()

    analyze_job_posting_task.delay(str(posting.id))
    return {"detail": "Analysis started.", "job_posting_id": str(posting.id)}


@router.get("/{posting_id}/analysis", response_model=GapAnalysisOut)
def get_latest_analysis(
    posting_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    posting = _get_owned_posting(posting_id, current_user, db)
    if not posting.analyses:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Analysis status: {posting.analysis_status}. Not ready yet.",
        )
    return posting.analyses[0]  # most recent, ordered in the relationship
