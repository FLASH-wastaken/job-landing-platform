from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import asyncio

from ..models.database import get_db
from ..models.schemas import Application, Candidate, ApplicationStatus
from ..services.auto_apply_agent import AutoApplyAgent, run_auto_apply_agent

router = APIRouter(prefix="/api/agent", tags=["agent"])

# In-memory state for the agent
_agent_status = {
    "running": False,
    "last_run": None,
    "last_result": None,
}


class AgentConfigRequest(BaseModel):
    min_match_score: int = 40
    max_jobs_per_candidate: int = 10
    search_limit: int = 20
    auto_tailor: bool = True
    auto_cover_letter: bool = True
    candidate_ids: Optional[list[int]] = None


class ApproveRequest(BaseModel):
    application_id: int
    action: str  # "approve" or "reject"


@router.post("/run")
async def trigger_agent_run(config: AgentConfigRequest = AgentConfigRequest()):
    """Manually trigger the auto-apply agent."""
    global _agent_status

    if _agent_status["running"]:
        raise HTTPException(status_code=409, detail="Agent is already running")

    _agent_status["running"] = True

    try:
        agent_config = {
            "min_match_score": config.min_match_score,
            "max_jobs_per_candidate": config.max_jobs_per_candidate,
            "search_limit": config.search_limit,
            "auto_tailor": config.auto_tailor,
            "auto_cover_letter": config.auto_cover_letter,
        }

        result = await run_auto_apply_agent(
            candidate_ids=config.candidate_ids,
            config=agent_config,
        )

        _agent_status["last_run"] = result.get("timestamp")
        _agent_status["last_result"] = result

        return result

    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        _agent_status["running"] = False


@router.get("/status")
def get_agent_status():
    """Get current agent status and last run info."""
    return _agent_status


@router.get("/queue")
def get_approval_queue(db: Session = Depends(get_db)):
    """Get applications discovered by the agent pending review."""
    apps = (
        db.query(Application)
        .filter(Application.status == ApplicationStatus.SAVED)
        .order_by(Application.match_score.desc())
        .all()
    )

    queue = []
    for app in apps:
        candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()
        queue.append({
            "id": app.id,
            "candidate_id": app.candidate_id,
            "candidate_name": candidate.name if candidate else "Unknown",
            "company": app.company_name,
            "title": app.job_title,
            "match_score": app.match_score,
            "location": app.location,
            "salary": app.salary_range,
            "url": app.job_url,
            "has_tailored_resume": bool(app.tailored_resume_text),
            "has_cover_letter": bool(app.cover_letter),
            "created_at": app.created_at.isoformat() if app.created_at else None,
        })

    return {"total": len(queue), "applications": queue}


@router.post("/approve")
def approve_or_reject(data: ApproveRequest, db: Session = Depends(get_db)):
    """Approve or reject an application from the agent queue."""
    app = db.query(Application).filter(Application.id == data.application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if data.action == "approve":
        app.status = ApplicationStatus.APPLIED
        from ..models.schemas import TimelineEvent
        db.add(TimelineEvent(
            application_id=app.id,
            event_type="approved",
            description="Approved from agent queue — marked as applied",
        ))
        db.commit()
        return {"message": f"Approved: {app.job_title} at {app.company_name}", "status": "applied"}

    elif data.action == "reject":
        app.status = ApplicationStatus.WITHDRAWN
        from ..models.schemas import TimelineEvent
        db.add(TimelineEvent(
            application_id=app.id,
            event_type="rejected",
            description="Rejected from agent queue",
        ))
        db.commit()
        return {"message": f"Rejected: {app.job_title} at {app.company_name}", "status": "withdrawn"}

    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")


@router.get("/config")
def get_agent_config():
    """Get current agent configuration defaults."""
    from ..services.auto_apply_agent import DEFAULT_CONFIG
    return DEFAULT_CONFIG
