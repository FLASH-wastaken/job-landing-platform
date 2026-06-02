from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone

from ..models.database import get_db
from ..models.schemas import JobAlert, AlertResult, Candidate, Application, ApplicationStatus, TimelineEvent
from ..services.alert_monitor import run_alert
from ..services.resume_tailor import generate_tailored_resume, generate_cover_letter_draft

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    candidate_id: int
    name: str
    search_query: str
    location: str = ""
    min_match_score: int = 30
    frequency_minutes: int = 60


class AlertUpdate(BaseModel):
    name: str | None = None
    search_query: str | None = None
    location: str | None = None
    min_match_score: int | None = None
    frequency_minutes: int | None = None
    is_active: bool | None = None


@router.get("")
def list_alerts(candidate_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(JobAlert)
    if candidate_id:
        query = query.filter(JobAlert.candidate_id == candidate_id)
    alerts = query.order_by(JobAlert.created_at.desc()).all()

    return [
        {
            "id": a.id,
            "candidate_id": a.candidate_id,
            "candidate_name": a.candidate.name,
            "name": a.name,
            "search_query": a.search_query,
            "location": a.location,
            "min_match_score": a.min_match_score,
            "frequency_minutes": a.frequency_minutes,
            "is_active": bool(a.is_active),
            "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            "total_found": a.total_found,
            "unseen_count": len([r for r in a.results if not r.is_seen]),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


@router.post("")
def create_alert(data: AlertCreate, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    alert = JobAlert(**data.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return {"id": alert.id, "message": f"Alert '{alert.name}' created"}


@router.put("/{alert_id}")
def update_alert(alert_id: int, data: AlertUpdate, db: Session = Depends(get_db)):
    alert = db.query(JobAlert).filter(JobAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    for field, value in data.model_dump(exclude_none=True).items():
        if field == "is_active":
            setattr(alert, field, 1 if value else 0)
        else:
            setattr(alert, field, value)

    db.commit()
    return {"message": "Alert updated"}


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(JobAlert).filter(JobAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    db.query(AlertResult).filter(AlertResult.alert_id == alert_id).delete()
    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted"}


@router.post("/{alert_id}/run")
async def trigger_alert(alert_id: int, db: Session = Depends(get_db)):
    """Manually trigger a single alert to search now."""
    alert = db.query(JobAlert).filter(JobAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    result = await run_alert(alert, db)
    return result


@router.get("/{alert_id}/results")
def get_alert_results(alert_id: int, unseen_only: bool = False, db: Session = Depends(get_db)):
    alert = db.query(JobAlert).filter(JobAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    query = db.query(AlertResult).filter(AlertResult.alert_id == alert_id)
    if unseen_only:
        query = query.filter(AlertResult.is_seen == 0)
    results = query.order_by(AlertResult.found_at.desc()).all()

    return [
        {
            "id": r.id,
            "job_title": r.job_title,
            "company": r.company,
            "url": r.url,
            "location": r.location,
            "salary": r.salary,
            "source": r.source,
            "match_score": r.match_score,
            "is_seen": bool(r.is_seen),
            "is_saved": bool(r.is_saved),
            "found_at": r.found_at.isoformat() if r.found_at else None,
        }
        for r in results
    ]


@router.put("/results/{result_id}/seen")
def mark_result_seen(result_id: int, db: Session = Depends(get_db)):
    result = db.query(AlertResult).filter(AlertResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    result.is_seen = 1
    db.commit()
    return {"message": "Marked as seen"}


@router.post("/results/{result_id}/save")
def save_result_to_pipeline(result_id: int, db: Session = Depends(get_db)):
    """Save an alert result as an application in the pipeline with ATS-optimized resume."""
    result = db.query(AlertResult).filter(AlertResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    alert = result.alert
    candidate = db.query(Candidate).filter(Candidate.id == alert.candidate_id).first()

    existing = (
        db.query(Application)
        .filter(
            Application.candidate_id == candidate.id,
            Application.company_name == result.company,
            Application.job_title == result.job_title,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Application already exists for this job")

    app = Application(
        candidate_id=candidate.id,
        company_name=result.company,
        job_title=result.job_title,
        job_url=result.url,
        salary_range=result.salary,
        location=result.location,
        status=ApplicationStatus.SAVED,
        match_score=result.match_score,
    )
    db.add(app)
    db.flush()

    db.add(TimelineEvent(
        application_id=app.id,
        event_type="alert_saved",
        description=f"Saved from job alert '{alert.name}' | Match: {result.match_score}%",
    ))

    result.is_saved = 1
    result.is_seen = 1
    db.commit()

    return {"id": app.id, "message": "Saved to pipeline"}


@router.post("/{alert_id}/mark-all-seen")
def mark_all_seen(alert_id: int, db: Session = Depends(get_db)):
    db.query(AlertResult).filter(
        AlertResult.alert_id == alert_id,
        AlertResult.is_seen == 0,
    ).update({"is_seen": 1})
    db.commit()
    return {"message": "All marked as seen"}


@router.get("/feed/all")
def get_alert_feed(db: Session = Depends(get_db)):
    """Get all unseen alert results across all alerts — the notification feed."""
    results = (
        db.query(AlertResult)
        .filter(AlertResult.is_seen == 0)
        .order_by(AlertResult.found_at.desc())
        .limit(50)
        .all()
    )

    return {
        "unseen_total": len(results),
        "results": [
            {
                "id": r.id,
                "alert_id": r.alert_id,
                "alert_name": r.alert.name,
                "candidate_name": r.alert.candidate.name,
                "job_title": r.job_title,
                "company": r.company,
                "url": r.url,
                "location": r.location,
                "salary": r.salary,
                "source": r.source,
                "match_score": r.match_score,
                "found_at": r.found_at.isoformat() if r.found_at else None,
            }
            for r in results
        ],
    }
