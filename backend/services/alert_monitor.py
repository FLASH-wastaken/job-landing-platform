"""
Job Alert Monitor

Runs periodically to check each active alert, searches job boards,
deduplicates against previously found jobs, and stores new matches.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models.database import SessionLocal
from ..models.schemas import JobAlert, AlertResult, Candidate
from .job_scraper import search_all_sources
from .resume_tailor import extract_keywords_from_job, compute_match_score


async def run_alert(alert: JobAlert, db: Session) -> dict:
    """Run a single alert: search, dedupe, score, store new results."""
    candidate = db.query(Candidate).filter(Candidate.id == alert.candidate_id).first()
    if not candidate:
        return {"alert_id": alert.id, "new_jobs": 0, "error": "candidate not found"}

    jobs = await search_all_sources(
        alert.search_query,
        location=alert.location or "",
        limit=20,
    )

    existing_keys = set()
    for r in alert.results:
        existing_keys.add((r.job_title.lower(), r.company.lower()))

    new_count = 0
    for job in jobs:
        key = (job["title"].lower(), job["company"].lower())
        if key in existing_keys:
            continue

        score = 0
        if candidate.base_resume_text and job.get("description"):
            jk = extract_keywords_from_job(job["description"])
            score = compute_match_score(candidate.base_resume_text, jk)
        elif candidate.skills:
            skills = [s.strip().lower() for s in candidate.skills.split(",")]
            desc = (job.get("description", "") + " " + job["title"]).lower()
            matched = sum(1 for s in skills if s in desc)
            score = round((matched / max(len(skills), 1)) * 100, 1)

        if score < alert.min_match_score:
            continue

        location_str = (
            job["location"] if isinstance(job.get("location"), str)
            else ", ".join(job.get("location", []))
        )

        db.add(AlertResult(
            alert_id=alert.id,
            job_title=job["title"],
            company=job["company"],
            url=job.get("url", ""),
            location=location_str,
            salary=job.get("salary", ""),
            source=job.get("source", "Unknown"),
            match_score=round(score, 1),
        ))
        new_count += 1
        existing_keys.add(key)

    alert.last_run_at = datetime.now(timezone.utc)
    alert.total_found = len(alert.results) + new_count
    db.commit()

    return {"alert_id": alert.id, "name": alert.name, "new_jobs": new_count}


async def run_all_alerts() -> list[dict]:
    """Run all active alerts. Called by the scheduler."""
    db = SessionLocal()
    try:
        alerts = db.query(JobAlert).filter(JobAlert.is_active == 1).all()
        results = []
        for alert in alerts:
            now = datetime.now(timezone.utc)
            if alert.last_run_at:
                elapsed = (now - alert.last_run_at).total_seconds() / 60
                if elapsed < alert.frequency_minutes:
                    continue
            result = await run_alert(alert, db)
            results.append(result)
        return results
    except Exception as e:
        print(f"[AlertMonitor] Error: {e}")
        return [{"error": str(e)}]
    finally:
        db.close()
