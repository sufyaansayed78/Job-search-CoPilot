from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Application, GapAnalysis, JobPosting, User, ApplicationStatus
from app.schemas import DashboardStats
from app.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Any status at or beyond this point counts as "got a response" for the
# response-rate calculation.
_RESPONDED_STATUSES = {
    ApplicationStatus.PHONE_SCREEN,
    ApplicationStatus.TECHNICAL,
    ApplicationStatus.ONSITE,
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
}


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    applications = db.query(Application).filter(Application.user_id == current_user.id).all()
    total = len(applications)

    by_status = {}
    for status_choice in ApplicationStatus:
        by_status[status_choice.value] = sum(1 for a in applications if a.status == status_choice)

    applied_or_later = [
        a for a in applications if a.status != ApplicationStatus.WISHLIST
    ]
    responded = [a for a in applied_or_later if a.status in _RESPONDED_STATUSES]
    response_rate = (
        round(len(responded) / len(applied_or_later) * 100, 1) if applied_or_later else 0.0
    )

    avg_score = (
        db.query(func.avg(GapAnalysis.match_score))
        .join(JobPosting, JobPosting.id == GapAnalysis.job_posting_id)
        .join(Application, Application.job_posting_id == JobPosting.id)
        .filter(
            Application.user_id == current_user.id,
            Application.status != ApplicationStatus.WISHLIST,
        )
        .scalar()
    )

    upcoming = (
        db.query(Application)
        .filter(
            Application.user_id == current_user.id,
            Application.follow_up_date.isnot(None),
            Application.follow_up_date >= datetime.now(timezone.utc),
        )
        .count()
    )

    return DashboardStats(
        total_applications=total,
        by_status=by_status,
        response_rate_pct=response_rate,
        avg_match_score_applied=round(avg_score, 1) if avg_score is not None else None,
        upcoming_follow_ups=upcoming,
    )
