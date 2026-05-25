import os
import json
import re


def extract_keywords_from_job(job_description: str) -> dict:
    """Extract key requirements, skills, and keywords from a job description."""
    sections = {
        "required_skills": [],
        "preferred_skills": [],
        "keywords": [],
        "experience_level": "",
        "key_responsibilities": [],
    }

    lines = job_description.split("\n")
    current_section = None

    skill_indicators = ["required", "must have", "essential", "minimum"]
    preferred_indicators = ["preferred", "nice to have", "bonus", "plus", "desired"]

    for line in lines:
        lower = line.lower().strip()
        if not lower:
            continue

        if any(ind in lower for ind in skill_indicators):
            current_section = "required_skills"
        elif any(ind in lower for ind in preferred_indicators):
            current_section = "preferred_skills"
        elif "responsibilit" in lower or "you will" in lower or "duties" in lower:
            current_section = "key_responsibilities"

        if current_section and (lower.startswith("-") or lower.startswith("*") or lower.startswith("•")):
            cleaned = re.sub(r"^[-*•]\s*", "", lower)
            sections[current_section].append(cleaned)

    words = re.findall(r"\b[A-Za-z][A-Za-z+#/.]+\b", job_description)
    common_tech = {
        "python", "javascript", "typescript", "react", "node", "aws", "azure",
        "gcp", "docker", "kubernetes", "sql", "nosql", "mongodb", "postgresql",
        "java", "c++", "c#", "go", "rust", "swift", "kotlin", "flutter",
        "machine learning", "ai", "data science", "devops", "ci/cd",
        "agile", "scrum", "rest", "api", "graphql", "microservices",
        "tensorflow", "pytorch", "pandas", "numpy", "spark", "hadoop",
        "tableau", "power bi", "excel", "salesforce", "hubspot",
        "figma", "sketch", "adobe", "photoshop", "illustrator",
    }
    for word in words:
        if word.lower() in common_tech:
            sections["keywords"].append(word)

    sections["keywords"] = list(set(sections["keywords"]))
    return sections


def compute_match_score(resume_text: str, job_keywords: dict) -> float:
    """Score how well a resume matches a job description (0-100)."""
    if not resume_text or not job_keywords:
        return 0.0

    resume_lower = resume_text.lower()
    total_items = 0
    matched_items = 0

    for skill in job_keywords.get("required_skills", []):
        total_items += 2
        if any(word in resume_lower for word in skill.split() if len(word) > 3):
            matched_items += 2

    for skill in job_keywords.get("preferred_skills", []):
        total_items += 1
        if any(word in resume_lower for word in skill.split() if len(word) > 3):
            matched_items += 1

    for keyword in job_keywords.get("keywords", []):
        total_items += 1.5
        if keyword.lower() in resume_lower:
            matched_items += 1.5

    if total_items == 0:
        return 50.0

    return round((matched_items / total_items) * 100, 1)


def generate_tailored_resume(base_resume: str, job_description: str, job_title: str, company_name: str) -> dict:
    """Generate a tailored resume based on the job description.

    Returns a dict with tailored_resume text, match_score, and suggestions.
    """
    job_keywords = extract_keywords_from_job(job_description)
    match_score = compute_match_score(base_resume, job_keywords)

    missing_keywords = []
    resume_lower = base_resume.lower()
    for kw in job_keywords.get("keywords", []):
        if kw.lower() not in resume_lower:
            missing_keywords.append(kw)

    tailoring_notes = []
    if missing_keywords:
        tailoring_notes.append(
            f"Consider incorporating these keywords naturally: {', '.join(missing_keywords)}"
        )

    if job_keywords.get("required_skills"):
        unmatched = []
        for skill in job_keywords["required_skills"]:
            if not any(word in resume_lower for word in skill.split() if len(word) > 3):
                unmatched.append(skill)
        if unmatched:
            tailoring_notes.append(
                f"Required skills not clearly shown in resume: {'; '.join(unmatched[:5])}"
            )

    tailored = base_resume

    summary_match = re.search(
        r"(summary|objective|profile|about)\s*:?\s*\n(.*?)(?=\n\n|\n[A-Z])",
        tailored,
        re.IGNORECASE | re.DOTALL,
    )
    if summary_match:
        old_summary = summary_match.group(0)
        new_summary_line = f"\nResults-driven professional targeting {job_title} role at {company_name}. "
        if job_keywords["keywords"]:
            top_kw = job_keywords["keywords"][:5]
            new_summary_line += f"Key expertise in {', '.join(top_kw)}."
        tailored = tailored.replace(
            old_summary,
            old_summary.split("\n")[0] + new_summary_line + "\n",
        )

    return {
        "tailored_resume": tailored,
        "match_score": match_score,
        "missing_keywords": missing_keywords,
        "tailoring_notes": tailoring_notes,
        "job_keywords": job_keywords,
    }


def generate_cover_letter_draft(
    candidate_name: str,
    job_title: str,
    company_name: str,
    resume_text: str,
    job_description: str,
) -> str:
    """Generate a cover letter draft."""
    job_keywords = extract_keywords_from_job(job_description)
    top_skills = job_keywords.get("keywords", [])[:5]
    skills_str = ", ".join(top_skills) if top_skills else "the required skills"

    return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company_name}. With my background and expertise in {skills_str}, I am confident I can make a meaningful contribution to your team.

[CUSTOMIZE: Add 2-3 specific accomplishments from your experience that directly relate to the job requirements]

[CUSTOMIZE: Mention something specific about {company_name} that excites you - a recent product launch, company mission, or industry position]

I am eager to bring my skills to {company_name} and would welcome the opportunity to discuss how my experience aligns with your team's needs.

Best regards,
{candidate_name}
"""
