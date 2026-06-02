from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from ..models.database import get_db
from ..models.schemas import Candidate, Application, ApplicationStatus
from ..services.linkedin_parser import parse_linkedin_pdf, parse_linkedin_text

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


class CandidateCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    field: str
    target_role: str
    target_salary_min: int | None = None
    target_salary_max: int | None = None
    location_preference: str | None = None
    linkedin_url: str | None = None
    base_resume_text: str | None = None
    skills: str | None = None
    years_experience: int | None = None


class CandidateUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    field: str | None = None
    target_role: str | None = None
    target_salary_min: int | None = None
    target_salary_max: int | None = None
    location_preference: str | None = None
    linkedin_url: str | None = None
    base_resume_text: str | None = None
    skills: str | None = None
    years_experience: int | None = None


@router.get("")
def list_candidates(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    results = []
    for c in candidates:
        app_count = db.query(Application).filter(Application.candidate_id == c.id).count()
        active_count = (
            db.query(Application)
            .filter(
                Application.candidate_id == c.id,
                Application.status.notin_([
                    ApplicationStatus.REJECTED,
                    ApplicationStatus.WITHDRAWN,
                    ApplicationStatus.OFFER_RECEIVED,
                ]),
            )
            .count()
        )
        results.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "field": c.field,
            "target_role": c.target_role,
            "location_preference": c.location_preference,
            "linkedin_url": c.linkedin_url,
            "skills": c.skills,
            "years_experience": c.years_experience,
            "total_applications": app_count,
            "active_applications": active_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return results


@router.get("/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    applications = (
        db.query(Application)
        .filter(Application.candidate_id == candidate_id)
        .order_by(Application.updated_at.desc())
        .all()
    )

    return {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "field": candidate.field,
        "target_role": candidate.target_role,
        "target_salary_min": candidate.target_salary_min,
        "target_salary_max": candidate.target_salary_max,
        "location_preference": candidate.location_preference,
        "linkedin_url": candidate.linkedin_url,
        "base_resume_text": candidate.base_resume_text,
        "skills": candidate.skills,
        "years_experience": candidate.years_experience,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "applications": [
            {
                "id": a.id,
                "company_name": a.company_name,
                "job_title": a.job_title,
                "status": a.status.value,
                "match_score": a.match_score,
                "applied_at": a.applied_at.isoformat() if a.applied_at else None,
                "last_status_change": a.last_status_change.isoformat() if a.last_status_change else None,
            }
            for a in applications
        ],
    }


@router.post("")
def create_candidate(data: CandidateCreate, db: Session = Depends(get_db)):
    candidate = Candidate(**data.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return {"id": candidate.id, "name": candidate.name, "message": "Candidate created"}


@router.put("/{candidate_id}")
def update_candidate(candidate_id: int, data: CandidateUpdate, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(candidate, key, value)

    db.commit()
    return {"message": "Candidate updated"}


@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    return {"message": "Candidate deleted"}


@router.post("/import-linkedin")
async def import_from_linkedin(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
):
    """Import candidate data from LinkedIn PDF export or pasted profile text."""
    if file:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        result = parse_linkedin_pdf(contents)
    elif text:
        result = parse_linkedin_text(text)
    else:
        raise HTTPException(status_code=400, detail="Provide either a PDF file or text")

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result
