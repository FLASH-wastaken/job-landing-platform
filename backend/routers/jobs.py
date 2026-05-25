from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio

from ..models.database import get_db
from ..models.schemas import Application, Candidate, TimelineEvent
from ..services.job_scraper import search_all_sources, scrape_career_page
from ..services.resume_tailor import generate_tailored_resume, generate_cover_letter_draft

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class CareerPageRequest(BaseModel):
    url: str


class SaveJobRequest(BaseModel):
    candidate_id: int
    title: str
    company: str
    url: str | None = None
    description: str | None = None
    location: str | None = None
    salary: str | None = None


@router.get("/search")
async def search_jobs(
    q: str = Query(..., description="Search query (job title, skills, etc.)"),
    location: str = Query("", description="Location filter"),
    limit: int = Query(15, ge=1, le=50),
):
    """Search for jobs across multiple free job APIs."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query is required")

    results = await search_all_sources(q.strip(), location.strip(), limit)
    return {
        "query": q,
        "location": location,
        "total_results": len(results),
        "jobs": results,
    }


@router.post("/scrape-careers")
async def scrape_career_page_endpoint(data: CareerPageRequest):
    """Scrape a company's career page for job listings."""
    if not data.url.startswith("http"):
        data.url = "https://" + data.url

    results = await scrape_career_page(data.url)
    return {
        "url": data.url,
        "total_results": len(results),
        "jobs": results,
    }


@router.post("/save")
def save_job_to_pipeline(data: SaveJobRequest, db: Session = Depends(get_db)):
    """Save a found job as an application for a candidate."""
    candidate = db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Check for duplicate
    existing = (
        db.query(Application)
        .filter(
            Application.candidate_id == data.candidate_id,
            Application.company_name == data.company,
            Application.job_title == data.title,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Application for {data.title} at {data.company} already exists",
        )

    app = Application(
        candidate_id=data.candidate_id,
        company_name=data.company,
        job_title=data.title,
        job_url=data.url,
        job_description=data.description,
        salary_range=data.salary,
        location=data.location,
    )

    # Auto-tailor resume if we have both resume and job description
    if data.description and candidate.base_resume_text:
        result = generate_tailored_resume(
            candidate.base_resume_text,
            data.description,
            data.title,
            data.company,
        )
        app.tailored_resume_text = result["tailored_resume"]
        app.match_score = result["match_score"]
        app.cover_letter = generate_cover_letter_draft(
            candidate.name,
            data.title,
            data.company,
            candidate.base_resume_text,
            data.description,
        )

    db.add(app)
    db.commit()
    db.refresh(app)

    db.add(TimelineEvent(
        application_id=app.id,
        event_type="created",
        description=f"Saved from job search: {data.title} at {data.company}",
    ))
    db.commit()

    return {
        "id": app.id,
        "match_score": app.match_score,
        "message": f"Saved {data.title} at {data.company} to pipeline",
    }
