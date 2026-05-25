from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..models.schemas import (
    Application,
    ApplicationStatus,
    Suggestion,
    SuggestionType,
    CompanyContact,
    TimelineEvent,
)


RULES = [
    {
        "trigger_status": ApplicationStatus.AWAITING_RESPONSE,
        "days_since_status": 3,
        "suggestion_type": SuggestionType.FOLLOW_UP_EMAIL,
        "title": "Send a follow-up email",
        "description_template": (
            "It's been {days} days since you applied to {company} for {title}. "
            "A polite follow-up can increase your response rate by 30%. "
            "Here's a draft you can customize."
        ),
        "priority": 8,
    },
    {
        "trigger_status": ApplicationStatus.AWAITING_RESPONSE,
        "days_since_status": 7,
        "suggestion_type": SuggestionType.LINKEDIN_OUTREACH,
        "title": "Reach out on LinkedIn",
        "description_template": (
            "No response after {days} days from {company}. "
            "Try reaching out directly to someone on the hiring team. "
            "We found a contact you can message."
        ),
        "priority": 9,
    },
    {
        "trigger_status": ApplicationStatus.AWAITING_RESPONSE,
        "days_since_status": 14,
        "suggestion_type": SuggestionType.MOVE_ON,
        "title": "Consider moving on",
        "description_template": (
            "It's been {days} days with no response from {company} for {title}. "
            "Consider focusing on other opportunities. "
            "Here are similar roles you might want to apply to."
        ),
        "priority": 6,
    },
    {
        "trigger_status": ApplicationStatus.INTERVIEW_SCHEDULED,
        "days_since_status": 0,
        "suggestion_type": SuggestionType.PREPARE_INTERVIEW,
        "title": "Prepare for your interview",
        "description_template": (
            "You have an interview coming up at {company} for {title}! "
            "Review the job description, research the company, and prepare "
            "STAR-format answers for behavioral questions."
        ),
        "priority": 10,
    },
    {
        "trigger_status": ApplicationStatus.FOLLOW_UP_SENT,
        "days_since_status": 5,
        "suggestion_type": SuggestionType.LINKEDIN_OUTREACH,
        "title": "Try a different contact",
        "description_template": (
            "Your follow-up to {company} hasn't gotten a response after {days} days. "
            "Try reaching out to a different person at the company."
        ),
        "priority": 7,
    },
]


def generate_follow_up_email(candidate_name: str, company: str, job_title: str, days: int) -> str:
    return f"""Subject: Following Up - {job_title} Application

Hi,

I hope this message finds you well. I recently applied for the {job_title} position at {company} and wanted to follow up on my application.

I'm very enthusiastic about this opportunity and believe my experience aligns well with what you're looking for. I'd love the chance to discuss how I can contribute to your team.

Would you have a few minutes this week for a brief conversation?

Thank you for your time and consideration.

Best regards,
{candidate_name}"""


def generate_linkedin_message(
    candidate_name: str,
    contact_name: str,
    contact_title: str,
    company: str,
    job_title: str,
) -> str:
    return f"""Hi {contact_name},

I recently applied for the {job_title} position at {company} and noticed your role as {contact_title}. I'd love to learn more about the team and the work you're doing.

Would you be open to a brief conversation? I'm passionate about this space and think my background could be a great fit.

Thanks for considering,
{candidate_name}"""


def run_suggestion_engine(db: Session) -> list[dict]:
    """Check all active applications and generate suggestions based on rules."""
    active_statuses = [
        ApplicationStatus.AWAITING_RESPONSE,
        ApplicationStatus.FOLLOW_UP_SENT,
        ApplicationStatus.INTERVIEW_SCHEDULED,
        ApplicationStatus.APPLIED,
    ]

    applications = (
        db.query(Application)
        .filter(Application.status.in_(active_statuses))
        .all()
    )

    new_suggestions = []
    now = datetime.now(timezone.utc)

    for app in applications:
        if app.status == ApplicationStatus.APPLIED:
            if app.applied_at:
                hours_since = (now - app.applied_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
                if hours_since >= 24:
                    app.status = ApplicationStatus.AWAITING_RESPONSE
                    app.last_status_change = now
                    db.add(TimelineEvent(
                        application_id=app.id,
                        event_type="status_change",
                        description="Auto-moved to Awaiting Response after 24 hours",
                    ))

        last_change = app.last_status_change
        if last_change and last_change.tzinfo is None:
            last_change = last_change.replace(tzinfo=timezone.utc)
        days_in_status = (now - last_change).days if last_change else 0

        for rule in RULES:
            if app.status != rule["trigger_status"]:
                continue
            if days_in_status < rule["days_since_status"]:
                continue

            existing = (
                db.query(Suggestion)
                .filter(
                    Suggestion.application_id == app.id,
                    Suggestion.suggestion_type == rule["suggestion_type"],
                    Suggestion.is_dismissed == 0,
                    Suggestion.is_completed == 0,
                )
                .first()
            )
            if existing:
                continue

            description = rule["description_template"].format(
                days=days_in_status,
                company=app.company_name,
                title=app.job_title,
            )

            draft_message = None
            target_contact_id = None

            if rule["suggestion_type"] == SuggestionType.FOLLOW_UP_EMAIL:
                draft_message = generate_follow_up_email(
                    app.candidate.name, app.company_name, app.job_title, days_in_status
                )
            elif rule["suggestion_type"] == SuggestionType.LINKEDIN_OUTREACH:
                contact = (
                    db.query(CompanyContact)
                    .filter(
                        CompanyContact.application_id == app.id,
                        CompanyContact.contacted == 0,
                    )
                    .first()
                )
                if contact:
                    target_contact_id = contact.id
                    draft_message = generate_linkedin_message(
                        app.candidate.name,
                        contact.name,
                        contact.title or "team member",
                        app.company_name,
                        app.job_title,
                    )

            suggestion = Suggestion(
                application_id=app.id,
                suggestion_type=rule["suggestion_type"],
                title=rule["title"],
                description=description,
                draft_message=draft_message,
                target_contact_id=target_contact_id,
                priority=rule["priority"],
            )
            db.add(suggestion)
            new_suggestions.append({
                "application": f"{app.job_title} at {app.company_name}",
                "suggestion": rule["title"],
                "priority": rule["priority"],
            })

    db.commit()
    return new_suggestions
