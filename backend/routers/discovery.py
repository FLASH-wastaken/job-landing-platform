from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.discovery_engine import get_quiz_questions, score_roles
from ..services.job_scraper import search_all_sources
from ..services.resume_tailor import (
    generate_tailored_resume,
    generate_cover_letter_draft,
    extract_keywords_from_job,
    compute_match_score,
)
from ..models.database import SessionLocal
from ..models.schemas import Candidate, Application, ApplicationStatus, TimelineEvent

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


class QuizAnswers(BaseModel):
    interests: list[str] = []
    skills: list[str] = []
    workstyle: dict = {}
    values: list[str] = []


class AutoApplyFromDiscovery(BaseModel):
    candidate_id: int
    roles: list[str]
    max_per_role: int = 5


@router.get("/quiz")
def get_quiz():
    """Return all quiz questions."""
    return get_quiz_questions()


@router.post("/results")
def compute_results(answers: QuizAnswers):
    """Score roles based on quiz answers and return ranked recommendations."""
    results = score_roles(answers.model_dump())
    top_roles = results[:8]
    return {
        "roles": top_roles,
        "total_scored": len(results),
    }


@router.post("/search-roles")
async def search_for_roles(body: dict):
    """Search job boards for specific roles from quiz results."""
    search_terms = body.get("search_terms", [])
    location = body.get("location", "")
    limit = body.get("limit", 10)

    all_jobs = []
    seen = set()
    for term in search_terms[:3]:
        jobs = await search_all_sources(term, location=location, limit=limit)
        for job in jobs:
            key = (job["title"].lower(), job["company"].lower())
            if key not in seen:
                seen.add(key)
                all_jobs.append(job)

    return {"jobs": all_jobs[:20], "total": len(all_jobs)}


@router.post("/auto-apply")
async def auto_apply_from_discovery(body: AutoApplyFromDiscovery):
    """
    Auto-apply to jobs for selected roles from discovery results.
    Creates applications with tailored resumes and cover letters.
    """
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.id == body.candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        total_discovered = 0
        total_applied = 0
        applied_jobs = []
        log = []

        for role in body.roles:
            log.append({"level": "info", "message": f"Searching for: {role}"})

            jobs = await search_all_sources(
                role,
                location=candidate.location_preference or "",
                limit=body.max_per_role * 2,
            )

            log.append({"level": "info", "message": f"Found {len(jobs)} listings for '{role}'"})
            total_discovered += len(jobs)

            queued = 0
            for job in jobs:
                if queued >= body.max_per_role:
                    break

                existing = (
                    db.query(Application)
                    .filter(
                        Application.candidate_id == candidate.id,
                        Application.company_name == job["company"],
                        Application.job_title == job["title"],
                    )
                    .first()
                )
                if existing:
                    continue

                score = 0
                ats = None
                tailored_resume = None
                cover_letter = None

                if candidate.base_resume_text and job.get("description"):
                    result = generate_tailored_resume(
                        candidate.base_resume_text,
                        job["description"],
                        job["title"],
                        job["company"],
                    )
                    tailored_resume = result["tailored_resume"]
                    score = result["match_score"]
                    ats = result.get("ats_score")

                    cover_letter = generate_cover_letter_draft(
                        candidate.name,
                        job["title"],
                        job["company"],
                        candidate.base_resume_text,
                        job["description"],
                    )
                elif candidate.skills:
                    skills = [s.strip().lower() for s in candidate.skills.split(",")]
                    desc = (job.get("description", "") + " " + job["title"]).lower()
                    matched = sum(1 for s in skills if s in desc)
                    score = round((matched / max(len(skills), 1)) * 100, 1)

                location_str = (
                    job["location"] if isinstance(job.get("location"), str)
                    else ", ".join(job.get("location", []))
                )

                app = Application(
                    candidate_id=candidate.id,
                    company_name=job["company"],
                    job_title=job["title"],
                    job_url=job.get("url", ""),
                    job_description=job.get("description", ""),
                    salary_range=job.get("salary", ""),
                    location=location_str,
                    status=ApplicationStatus.SAVED,
                    match_score=round(score, 1),
                    ats_score=ats,
                    tailored_resume_text=tailored_resume,
                    cover_letter=cover_letter,
                )
                db.add(app)
                db.flush()

                db.add(TimelineEvent(
                    application_id=app.id,
                    event_type="discovery_auto_apply",
                    description=(
                        f"Auto-applied from Discovery Quiz | Role: {role} | "
                        f"Match: {app.match_score}% | Source: {job.get('source', 'Unknown')}"
                    ),
                ))

                queued += 1
                total_applied += 1
                applied_jobs.append({
                    "title": job["title"],
                    "company": job["company"],
                    "score": app.match_score,
                    "has_tailored_resume": tailored_resume is not None,
                    "has_cover_letter": cover_letter is not None,
                    "source": job.get("source", "Unknown"),
                })
                log.append({
                    "level": "info",
                    "message": f"  Queued: {job['title']} at {job['company']} ({app.match_score}% match)"
                })

        db.commit()

        return {
            "status": "completed",
            "total_discovered": total_discovered,
            "total_applied": total_applied,
            "jobs": applied_jobs,
            "log": log,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
