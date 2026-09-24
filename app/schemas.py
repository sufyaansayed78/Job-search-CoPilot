import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models import ApplicationStatus


# ─── Auth ──────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    email: str
    resume_text: str
    created_at: datetime


class ResumeUpdate(BaseModel):
    resume_text: str


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


# ─── Company ───────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    website: str = ""
    notes: str = ""


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    website: str
    notes: str
    created_at: datetime


# ─── Job posting ───────────────────────────────────────────────────────────

class JobPostingCreate(BaseModel):
    company_id: uuid.UUID
    title: str
    url: str = ""
    source: str = "manual"
    raw_description: str


class JobPostingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    url: str
    source: str
    raw_description: str
    analysis_status: str
    created_at: datetime


class GapAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: uuid.UUID
    match_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    required_skills: list[str]
    seniority_level: str
    recommendation: str
    summary: str
    model_version: str
    created_at: datetime


# ─── Application ───────────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    job_posting_id: uuid.UUID
    status: ApplicationStatus = ApplicationStatus.WISHLIST
    resume_version: str = ""
    applied_date: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    notes: str = ""


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    job_posting_id: uuid.UUID
    status: ApplicationStatus
    resume_version: str
    applied_date: Optional[datetime]
    follow_up_date: Optional[datetime]
    notes: str
    created_at: datetime
    updated_at: datetime


# ─── Dashboard ─────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_applications: int
    by_status: dict
    response_rate_pct: float  # (phone_screen or later) / applied
    avg_match_score_applied: Optional[float]
    upcoming_follow_ups: int
