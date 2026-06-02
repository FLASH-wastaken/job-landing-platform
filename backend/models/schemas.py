from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from .database import Base


class ApplicationStatus(enum.Enum):
    SAVED = "saved"
    TAILORING = "tailoring"
    APPLIED = "applied"
    AWAITING_RESPONSE = "awaiting_response"
    FOLLOW_UP_SENT = "follow_up_sent"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_RECEIVED = "offer_received"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class SuggestionType(enum.Enum):
    FOLLOW_UP_EMAIL = "follow_up_email"
    LINKEDIN_OUTREACH = "linkedin_outreach"
    APPLY_SIMILAR = "apply_similar"
    MOVE_ON = "move_on"
    PREPARE_INTERVIEW = "prepare_interview"


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150))
    phone = Column(String(20))
    field = Column(String(100), nullable=False)
    target_role = Column(String(150), nullable=False)
    target_salary_min = Column(Integer)
    target_salary_max = Column(Integer)
    location_preference = Column(String(200))
    linkedin_url = Column(String(300))
    base_resume_text = Column(Text)
    base_resume_path = Column(String(500))
    skills = Column(Text)
    years_experience = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    applications = relationship("Application", back_populates="candidate")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    company_name = Column(String(200), nullable=False)
    job_title = Column(String(200), nullable=False)
    job_url = Column(String(500))
    job_description = Column(Text)
    salary_range = Column(String(100))
    location = Column(String(200))
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.SAVED)
    tailored_resume_text = Column(Text)
    tailored_resume_path = Column(String(500))
    cover_letter = Column(Text)
    match_score = Column(Float)
    ats_score = Column(Float)
    notes = Column(Text)
    applied_at = Column(DateTime)
    last_status_change = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    candidate = relationship("Candidate", back_populates="applications")
    contacts = relationship("CompanyContact", back_populates="application")
    suggestions = relationship("Suggestion", back_populates="application")
    timeline = relationship("TimelineEvent", back_populates="application")


class CompanyContact(Base):
    __tablename__ = "company_contacts"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    name = Column(String(150), nullable=False)
    title = Column(String(200))
    linkedin_url = Column(String(300))
    email = Column(String(200))
    relationship_type = Column(String(50))
    contacted = Column(Integer, default=0)
    contacted_at = Column(DateTime)
    response_received = Column(Integer, default=0)

    application = relationship("Application", back_populates="contacts")


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    suggestion_type = Column(Enum(SuggestionType), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    draft_message = Column(Text)
    target_contact_id = Column(Integer, ForeignKey("company_contacts.id"))
    priority = Column(Integer, default=5)
    is_dismissed = Column(Integer, default=0)
    is_completed = Column(Integer, default=0)
    triggered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)

    application = relationship("Application", back_populates="suggestions")


class JobAlert(Base):
    __tablename__ = "job_alerts"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    name = Column(String(200), nullable=False)
    search_query = Column(String(300), nullable=False)
    location = Column(String(200), default="")
    min_match_score = Column(Integer, default=30)
    is_active = Column(Integer, default=1)
    frequency_minutes = Column(Integer, default=60)
    last_run_at = Column(DateTime)
    total_found = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    candidate = relationship("Candidate")
    results = relationship("AlertResult", back_populates="alert")


class AlertResult(Base):
    __tablename__ = "alert_results"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("job_alerts.id"), nullable=False)
    job_title = Column(String(300), nullable=False)
    company = Column(String(200), nullable=False)
    url = Column(String(500))
    location = Column(String(200))
    salary = Column(String(100))
    source = Column(String(100))
    match_score = Column(Float)
    is_seen = Column(Integer, default=0)
    is_saved = Column(Integer, default=0)
    found_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    alert = relationship("JobAlert", back_populates="results")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="timeline")
