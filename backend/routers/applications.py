from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone

from ..models.database import get_db
from ..models.schemas import (
    Application,
    ApplicationStatus,
    Candidate,
    CompanyContact,
    TimelineEvent,
    Suggestion,
)
from ..services.resume_tailor import (
    generate_tailored_resume,
    generate_cover_letter_draft,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])


class ApplicationCreate(BaseModel):
    candidate_id: int
    company_name: str
    job_title: str
    job_url: str | None = None
    job_description: str | None = None
    salary_range: str | None = None
    location: str | None = None
    notes: str | None = None


class StatusUpdate(BaseModel):
    status: str
    notes: str | None = None


class ContactCreate(BaseModel):
    name: str
    title: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    relationship_type: str | None = None


@router.get("")
def list_applications(
    candidate_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Application)
    if candidate_id:
        query = query.filter(Application.candidate_id == candidate_id)
    if status:
        try:
            status_enum = ApplicationStatus(status)
            query = query.filter(Application.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    applications = query.order_by(Application.updated_at.desc()).all()

    return [
        {
            "id": a.id,
            "candidate_id": a.candidate_id,
            "candidate_name": a.candidate.name,
            "company_name": a.company_name,
            "job_title": a.job_title,
            "job_url": a.job_url,
            "status": a.status.value,
            "match_score": a.match_score,
            "ats_score": a.ats_score,
            "salary_range": a.salary_range,
            "location": a.location,
            "applied_at": a.applied_at.isoformat() if a.applied_at else None,
            "last_status_change": a.last_status_change.isoformat() if a.last_status_change else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "suggestion_count": len([s for s in a.suggestions if not s.is_dismissed and not s.is_completed]),
            "contact_count": len(a.contacts),
        }
        for a in applications
    ]


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "id": app.id,
        "candidate_id": app.candidate_id,
        "candidate_name": app.candidate.name,
        "company_name": app.company_name,
        "job_title": app.job_title,
        "job_url": app.job_url,
        "job_description": app.job_description,
        "status": app.status.value,
        "match_score": app.match_score,
        "ats_score": app.ats_score,
        "salary_range": app.salary_range,
        "location": app.location,
        "tailored_resume_text": app.tailored_resume_text,
        "cover_letter": app.cover_letter,
        "notes": app.notes,
        "applied_at": app.applied_at.isoformat() if app.applied_at else None,
        "last_status_change": app.last_status_change.isoformat() if app.last_status_change else None,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "title": c.title,
                "linkedin_url": c.linkedin_url,
                "email": c.email,
                "relationship_type": c.relationship_type,
                "contacted": bool(c.contacted),
                "response_received": bool(c.response_received),
            }
            for c in app.contacts
        ],
        "suggestions": [
            {
                "id": s.id,
                "type": s.suggestion_type.value,
                "title": s.title,
                "description": s.description,
                "draft_message": s.draft_message,
                "priority": s.priority,
                "is_completed": bool(s.is_completed),
                "is_dismissed": bool(s.is_dismissed),
                "triggered_at": s.triggered_at.isoformat() if s.triggered_at else None,
            }
            for s in app.suggestions
        ],
        "timeline": [
            {
                "id": t.id,
                "event_type": t.event_type,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in sorted(app.timeline, key=lambda x: x.created_at, reverse=True)
        ],
    }


@router.post("")
def create_application(data: ApplicationCreate, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    app = Application(**data.model_dump())

    if data.job_description and candidate.base_resume_text:
        result = generate_tailored_resume(
            candidate.base_resume_text,
            data.job_description,
            data.job_title,
            data.company_name,
        )
        app.tailored_resume_text = result["tailored_resume"]
        app.match_score = result["match_score"]
        app.ats_score = result.get("ats_score")

        app.cover_letter = generate_cover_letter_draft(
            candidate.name,
            data.job_title,
            data.company_name,
            candidate.base_resume_text,
            data.job_description,
        )

    db.add(app)
    db.commit()
    db.refresh(app)

    db.add(TimelineEvent(
        application_id=app.id,
        event_type="created",
        description=f"Application created for {data.job_title} at {data.company_name}",
    ))
    db.commit()

    return {
        "id": app.id,
        "match_score": app.match_score,
        "ats_score": app.ats_score,
        "message": "Application created with ATS-optimized resume",
    }


@router.put("/{app_id}/status")
def update_status(app_id: int, data: StatusUpdate, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        new_status = ApplicationStatus(data.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    old_status = app.status
    app.status = new_status
    app.last_status_change = datetime.now(timezone.utc)

    if new_status == ApplicationStatus.APPLIED and not app.applied_at:
        app.applied_at = datetime.now(timezone.utc)

    if data.notes:
        app.notes = (app.notes or "") + f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d')}] {data.notes}"

    db.add(TimelineEvent(
        application_id=app.id,
        event_type="status_change",
        description=f"Status changed from {old_status.value} to {new_status.value}"
        + (f" - {data.notes}" if data.notes else ""),
    ))
    db.commit()

    return {"message": f"Status updated to {new_status.value}"}


@router.post("/{app_id}/contacts")
def add_contact(app_id: int, data: ContactCreate, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    contact = CompanyContact(application_id=app_id, **data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return {"id": contact.id, "message": "Contact added"}


@router.post("/{app_id}/tailor")
def retailor_resume(app_id: int, db: Session = Depends(get_db)):
    """Re-generate tailored resume for an application."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    candidate = app.candidate
    if not candidate.base_resume_text:
        raise HTTPException(status_code=400, detail="Candidate has no base resume")
    if not app.job_description:
        raise HTTPException(status_code=400, detail="No job description to tailor against")

    result = generate_tailored_resume(
        candidate.base_resume_text,
        app.job_description,
        app.job_title,
        app.company_name,
    )
    app.tailored_resume_text = result["tailored_resume"]
    app.match_score = result["match_score"]
    app.ats_score = result.get("ats_score")

    app.cover_letter = generate_cover_letter_draft(
        candidate.name,
        app.job_title,
        app.company_name,
        candidate.base_resume_text,
        app.job_description,
    )

    db.commit()

    return {
        "match_score": result["match_score"],
        "ats_score": result.get("ats_score"),
        "ats_breakdown": result.get("ats_breakdown"),
        "missing_keywords": result["missing_keywords"],
        "tailoring_notes": result["tailoring_notes"],
        "message": "Resume re-tailored with ATS optimization",
    }


@router.put("/suggestions/{suggestion_id}/dismiss")
def dismiss_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    suggestion.is_dismissed = 1
    db.commit()
    return {"message": "Suggestion dismissed"}


@router.put("/suggestions/{suggestion_id}/complete")
def complete_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    suggestion.is_completed = 1
    suggestion.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Suggestion completed"}
