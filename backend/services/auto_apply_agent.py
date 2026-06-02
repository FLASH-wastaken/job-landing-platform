"""
Auto-Apply Agent
Autonomous job discovery, matching, tailoring, and application pipeline.

Pipeline:
1. DISCOVER  - Search job boards for each candidate's target role + skills
2. SCORE     - Match score against resume, filter by threshold
3. TAILOR    - Generate tailored resume + cover letter
4. QUEUE     - Add to approval queue for human review
5. APPLY     - On approval, mark as applied and draft outreach
"""

import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..models.database import SessionLocal
from ..models.schemas import (
    Candidate,
    Application,
    ApplicationStatus,
    TimelineEvent,
)
from .job_scraper import search_all_sources
from .resume_tailor import (
    generate_tailored_resume,
    generate_cover_letter_draft,
    compute_match_score,
    extract_keywords_from_job,
)


# Agent configuration
DEFAULT_CONFIG = {
    "min_match_score": 40,        # Minimum match score to queue (0-100)
    "max_jobs_per_candidate": 10, # Max jobs to queue per run per candidate
    "search_limit": 20,           # How many results to fetch per search
    "auto_tailor": True,          # Auto-generate tailored resumes
    "auto_cover_letter": True,    # Auto-generate cover letters
}


class AutoApplyAgent:
    """Autonomous agent that finds, scores, and prepares job applications."""

    def __init__(self, config: dict = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.run_log = []

    def log(self, message: str, level: str = "info"):
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        self.run_log.append(entry)
        print(f"[AutoApplyAgent] [{level.upper()}] {message}")

    async def run(self, candidate_ids: list[int] = None) -> dict:
        """
        Run the full agent pipeline.
        If candidate_ids is None, runs for all candidates.
        Returns a summary of actions taken.
        """
        self.run_log = []
        self.log("Agent run started")

        db = SessionLocal()
        try:
            # Get candidates to process
            if candidate_ids:
                candidates = db.query(Candidate).filter(
                    Candidate.id.in_(candidate_ids)
                ).all()
            else:
                candidates = db.query(Candidate).all()

            if not candidates:
                self.log("No candidates found", "warning")
                return {"status": "no_candidates", "log": self.run_log}

            self.log(f"Processing {len(candidates)} candidate(s)")

            total_discovered = 0
            total_qualified = 0
            total_queued = 0
            candidate_results = []

            for candidate in candidates:
                result = await self._process_candidate(db, candidate)
                candidate_results.append(result)
                total_discovered += result["discovered"]
                total_qualified += result["qualified"]
                total_queued += result["queued"]

            db.commit()

            summary = {
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "candidates_processed": len(candidates),
                "total_discovered": total_discovered,
                "total_qualified": total_qualified,
                "total_queued": total_queued,
                "candidates": candidate_results,
                "log": self.run_log,
            }

            self.log(
                f"Agent run complete: {total_discovered} discovered, "
                f"{total_qualified} qualified, {total_queued} queued"
            )

            return summary

        except Exception as e:
            self.log(f"Agent error: {str(e)}", "error")
            db.rollback()
            return {"status": "error", "error": str(e), "log": self.run_log}
        finally:
            db.close()

    async def _process_candidate(self, db: Session, candidate: Candidate) -> dict:
        """Process a single candidate through the agent pipeline."""
        self.log(f"--- Processing: {candidate.name} ({candidate.target_role}) ---")

        result = {
            "candidate_id": candidate.id,
            "candidate_name": candidate.name,
            "target_role": candidate.target_role,
            "discovered": 0,
            "qualified": 0,
            "queued": 0,
            "skipped_duplicates": 0,
            "jobs": [],
        }

        # Build search queries from candidate profile
        queries = self._build_search_queries(candidate)
        self.log(f"Search queries: {queries}")

        # STEP 1: DISCOVER - Search for jobs
        all_jobs = []
        for query in queries:
            jobs = await search_all_sources(
                query,
                location=candidate.location_preference or "",
                limit=self.config["search_limit"],
            )
            all_jobs.extend(jobs)

        # Deduplicate
        seen = set()
        unique_jobs = []
        for job in all_jobs:
            key = (job["title"].lower(), job["company"].lower())
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)

        result["discovered"] = len(unique_jobs)
        self.log(f"Discovered {len(unique_jobs)} unique jobs")

        if not unique_jobs:
            return result

        # STEP 2: SCORE & FILTER
        scored_jobs = []
        for job in unique_jobs:
            # Check for duplicates in existing applications
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
                result["skipped_duplicates"] += 1
                continue

            # Score the match
            score = 0
            if candidate.base_resume_text and job.get("description"):
                job_keywords = extract_keywords_from_job(job["description"])
                score = compute_match_score(candidate.base_resume_text, job_keywords, job["title"])
            elif candidate.skills:
                # Fallback: check skill overlap
                skills = [s.strip().lower() for s in candidate.skills.split(",")]
                desc_lower = (job.get("description", "") + " " + job["title"]).lower()
                matched = sum(1 for s in skills if s in desc_lower)
                score = (matched / max(len(skills), 1)) * 100 if skills else 50

            if score >= self.config["min_match_score"]:
                scored_jobs.append({"job": job, "score": score})

        # Sort by score descending
        scored_jobs.sort(key=lambda x: x["score"], reverse=True)

        # Cap at max per candidate
        scored_jobs = scored_jobs[: self.config["max_jobs_per_candidate"]]
        result["qualified"] = len(scored_jobs)
        self.log(f"{len(scored_jobs)} jobs passed score threshold (>={self.config['min_match_score']})")

        # STEP 3 & 4: TAILOR & QUEUE
        for item in scored_jobs:
            job = item["job"]
            score = item["score"]

            try:
                app = Application(
                    candidate_id=candidate.id,
                    company_name=job["company"],
                    job_title=job["title"],
                    job_url=job.get("url", ""),
                    job_description=job.get("description", ""),
                    salary_range=job.get("salary", ""),
                    location=job["location"] if isinstance(job["location"], str)
                             else ", ".join(job.get("location", [])),
                    status=ApplicationStatus.SAVED,
                    match_score=round(score, 1),
                )

                # Auto-tailor resume
                if (
                    self.config["auto_tailor"]
                    and candidate.base_resume_text
                    and job.get("description")
                ):
                    tailor_result = generate_tailored_resume(
                        candidate.base_resume_text,
                        job["description"],
                        job["title"],
                        job["company"],
                    )
                    app.tailored_resume_text = tailor_result["tailored_resume"]
                    app.match_score = tailor_result["match_score"]
                    app.ats_score = tailor_result.get("ats_score")

                # Auto-generate cover letter
                if (
                    self.config["auto_cover_letter"]
                    and candidate.base_resume_text
                    and job.get("description")
                ):
                    app.cover_letter = generate_cover_letter_draft(
                        candidate.name,
                        job["title"],
                        job["company"],
                        candidate.base_resume_text,
                        job["description"],
                    )

                db.add(app)
                db.flush()  # Get the ID

                # Add timeline event
                db.add(TimelineEvent(
                    application_id=app.id,
                    event_type="auto_discovered",
                    description=(
                        f"Auto-discovered by agent | Match: {app.match_score}% | "
                        f"Source: {job.get('source', 'Unknown')}"
                    ),
                ))

                result["queued"] += 1
                result["jobs"].append({
                    "title": job["title"],
                    "company": job["company"],
                    "score": app.match_score,
                    "source": job.get("source", "Unknown"),
                    "status": "queued",
                })

                self.log(
                    f"  Queued: {job['title']} at {job['company']} "
                    f"(score: {app.match_score}%)"
                )

            except Exception as e:
                self.log(f"  Error queuing {job['title']}: {str(e)}", "error")

        return result

    def _build_search_queries(self, candidate: Candidate) -> list[str]:
        """Build smart search queries from candidate profile."""
        queries = []

        # Primary: target role
        if candidate.target_role:
            queries.append(candidate.target_role)

        # Secondary: field + top skills
        if candidate.skills:
            skills = [s.strip() for s in candidate.skills.split(",")]
            top_skills = skills[:3]
            if candidate.field:
                queries.append(f"{candidate.field} {' '.join(top_skills)}")

        # If we only have the field
        if not queries and candidate.field:
            queries.append(candidate.field)

        return queries[:3]  # Max 3 queries


async def run_auto_apply_agent(
    candidate_ids: list[int] = None,
    config: dict = None,
) -> dict:
    """Convenience function to run the agent."""
    agent = AutoApplyAgent(config)
    return await agent.run(candidate_ids)


def run_scheduled_agent():
    """Entry point for the background scheduler."""
    print("[Scheduler] Running auto-apply agent...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_auto_apply_agent())
        print(f"[Scheduler] Agent complete: {result.get('total_queued', 0)} jobs queued")
    except Exception as e:
        print(f"[Scheduler] Agent error: {e}")
    finally:
        loop.close()
