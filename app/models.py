 import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, Float, Enum, JSON,
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.db_types import GUID


def _uuid():
    return uuid.uuid4()


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    # Free-text skills/resume summary the agent compares every JD against.
    # Kept as plain text rather than a structured schema so the user can
    # paste their actual resume text in directly.
    resume_text = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    companies = relationship("Company", back_populates="owner", cascade="all, delete-orphan")
    job_postings = relationship("JobPosting", back_populates="owner", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="owner", cascade="all, delete-orphan")


class Company(Base):
    __tablename__ = "companies"

    id = Column(GUID(), primary_key=True, default=_uuid)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    name = Column(String(150), nullable=False)
    website = Column(String(255), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)

    owner = relationship("User", back_populates="companies")
    job_postings = relationship("JobPosting", back_populates="company", cascade="all, delete-orphan")


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(GUID(), primary_key=True, default=_uuid)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    company_id = Column(GUID(), ForeignKey("companies.id"), nullable=False)
    title = Column(String(200), nullable=False)
    url = Column(String(500), default="")
    source = Column(String(50), default="manual")  # manual, linkedin, company-site, referral...
    raw_description = Column(Text, nullable=False)  # the JD, pasted in by the user
    analysis_status = Column(String(20), default="not_started")  # not_started, pending, done, failed
    created_at = Column(DateTime(timezone=True), default=_now)

    owner = relationship("User", back_populates="job_postings")
    company = relationship("Company", back_populates="job_postings")
    applications = relationship("Application", back_populates="job_posting", cascade="all, delete-orphan")
    analyses = relationship(
        "GapAnalysis", back_populates="job_posting",
        cascade="all, delete-orphan", order_by="desc(GapAnalysis.created_at)",
    )


class ApplicationStatus(str, enum.Enum):
    WISHLIST = "wishlist"
    APPLIED = "applied"
    PHONE_SCREEN = "phone_screen"
    TECHNICAL = "technical"
    ONSITE = "onsite"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Application(Base):
    __tablename__ = "applications"

    id = Column(GUID(), primary_key=True, default=_uuid)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    job_posting_id = Column(GUID(), ForeignKey("job_postings.id"), nullable=False)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.WISHLIST, nullable=False)
    resume_version = Column(String(100), default="")  # e.g. "backend-focused-v2"
    applied_date = Column(DateTime(timezone=True), nullable=True)
    follow_up_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    owner = relationship("User", back_populates="applications")
    job_posting = relationship("JobPosting", back_populates="applications")


class GapAnalysis(Base):
    """Output of the LangGraph agent for one job posting."""
    __tablename__ = "gap_analyses"

    id = Column(GUID(), primary_key=True, default=_uuid)
    job_posting_id = Column(GUID(), ForeignKey("job_postings.id"), nullable=False)
    match_score = Column(Float, nullable=False)  # 0-100
    matched_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    required_skills = Column(JSON, default=list)
    seniority_level = Column(String(50), default="")
    recommendation = Column(String(20), default="")  # strong_fit, stretch, skip
    summary = Column(Text, default="")  # what to emphasise in the application
    model_version = Column(String(50), default="")
    created_at = Column(DateTime(timezone=True), default=_now)

    job_posting = relationship("JobPosting", back_populates="analyses")
