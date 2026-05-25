from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.database import get_db
from ..models.schemas import (
    Application,
    ApplicationStatus,
    Candidate,
    Suggestion,
)
from ..services.suggestion_engine import run_suggestion_engine

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db)):
    """Main dashboard data - overview of all candidates and their pipelines."""
    candidates = db.query(Candidate).all()

    pipeline_counts = {}
    for status in ApplicationStatus:
        count = db.query(Application).filter(Application.status == status).count()
        pipeline_counts[status.value] = count

    pending_suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.is_dismissed == 0, Suggestion.is_completed == 0)
        .order_by(Suggestion.priority.desc())
        .limit(20)
        .all()
    )

    candidate_summaries = []
    for c in candidates:
        apps = db.query(Application).filter(Application.candidate_id == c.id).all()
        status_breakdown = {}
        for a in apps:
            status_breakdown[a.status.value] = status_breakdown.get(a.status.value, 0) + 1

        avg_score = None
        scores = [a.match_score for a in apps if a.match_score is not None]
        if scores:
            avg_score = round(sum(scores) / len(scores), 1)

        active_suggestions = (
            db.query(Suggestion)
            .join(Application)
            .filter(
                Application.candidate_id == c.id,
                Suggestion.is_dismissed == 0,
                Suggestion.is_completed == 0,
            )
            .count()
        )

        candidate_summaries.append({
            "id": c.id,
            "name": c.name,
            "field": c.field,
            "target_role": c.target_role,
            "total_applications": len(apps),
            "status_breakdown": status_breakdown,
            "avg_match_score": avg_score,
            "pending_actions": active_suggestions,
        })

    return {
        "total_candidates": len(candidates),
        "total_applications": sum(pipeline_counts.values()),
        "pipeline": pipeline_counts,
        "candidates": candidate_summaries,
        "top_suggestions": [
            {
                "id": s.id,
                "application_id": s.application_id,
                "type": s.suggestion_type.value,
                "title": s.title,
                "description": s.description,
                "priority": s.priority,
                "draft_message": s.draft_message,
                "triggered_at": s.triggered_at.isoformat() if s.triggered_at else None,
                "company": s.application.company_name,
                "job_title": s.application.job_title,
                "candidate_name": s.application.candidate.name,
            }
            for s in pending_suggestions
        ],
    }


@router.post("/refresh-suggestions")
def refresh_suggestions(db: Session = Depends(get_db)):
    """Run the suggestion engine to generate new action items."""
    new_suggestions = run_suggestion_engine(db)
    return {
        "new_suggestions": len(new_suggestions),
        "details": new_suggestions,
    }
