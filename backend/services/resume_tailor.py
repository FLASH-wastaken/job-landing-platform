import re


# Expanded keyword database — ATS systems scan for exact matches
TECH_KEYWORDS = {
    "python", "javascript", "typescript", "react", "angular", "vue", "node",
    "express", "django", "flask", "fastapi", "spring", "rails",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "sql", "nosql", "mongodb", "postgresql", "mysql", "redis", "elasticsearch",
    "java", "c++", "c#", "go", "rust", "swift", "kotlin", "flutter", "dart",
    "machine learning", "deep learning", "ai", "nlp", "computer vision",
    "data science", "data engineering", "data analytics",
    "devops", "ci/cd", "jenkins", "github actions", "gitlab",
    "agile", "scrum", "kanban", "jira", "confluence",
    "rest", "api", "graphql", "grpc", "microservices", "serverless",
    "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn", "spark", "hadoop",
    "tableau", "power bi", "looker", "excel", "google sheets",
    "salesforce", "hubspot", "marketo", "segment",
    "figma", "sketch", "adobe", "photoshop", "illustrator", "invision",
    "html", "css", "sass", "tailwind", "bootstrap", "webpack", "vite",
    "git", "linux", "bash", "powershell",
    "oauth", "jwt", "saml", "sso",
    "unit testing", "integration testing", "selenium", "cypress", "jest",
    "kafka", "rabbitmq", "celery", "airflow",
    "networking", "tcp/ip", "dns", "load balancing", "cdn",
    "seo", "sem", "google analytics", "a/b testing",
    "project management", "stakeholder management", "cross-functional",
    "leadership", "mentoring", "team management",
}

# Multi-word phrases to detect in JD (ATS systems match these as complete phrases)
PHRASE_KEYWORDS = [
    "machine learning", "deep learning", "data science", "data engineering",
    "data analytics", "computer vision", "natural language processing",
    "ci/cd", "unit testing", "integration testing", "a/b testing",
    "project management", "stakeholder management", "team management",
    "cross-functional", "google analytics", "power bi", "google sheets",
    "github actions", "load balancing", "scikit-learn",
]

# Experience level patterns
EXP_PATTERNS = [
    (r"(\d+)\+?\s*years", "years"),
    (r"senior|sr\.", "senior"),
    (r"junior|jr\.|entry.level", "junior"),
    (r"mid.level|intermediate", "mid"),
    (r"lead|principal|staff", "lead"),
    (r"manager|director|head of", "manager"),
]

# ATS-friendly section headers — systems expect these exact strings
ATS_SECTION_HEADERS = {
    "summary", "professional summary", "objective", "profile",
    "experience", "work experience", "professional experience", "employment",
    "education", "skills", "technical skills", "core competencies",
    "certifications", "projects", "achievements",
}

# Strong action verbs that ATS and recruiters look for
ACTION_VERBS = [
    "achieved", "built", "created", "delivered", "developed", "designed",
    "drove", "engineered", "established", "executed", "generated",
    "implemented", "improved", "increased", "launched", "led", "managed",
    "optimized", "orchestrated", "reduced", "scaled", "shipped",
    "spearheaded", "streamlined", "transformed",
]


def extract_keywords_from_job(job_description: str) -> dict:
    """Extract key requirements, skills, and keywords from a job description.

    Enhanced for ATS: extracts exact phrases, experience level, soft skills,
    and the job title variants that ATS systems index on.
    """
    sections = {
        "required_skills": [],
        "preferred_skills": [],
        "keywords": [],
        "experience_level": "",
        "key_responsibilities": [],
        "soft_skills": [],
        "job_title_variants": [],
    }

    jd_lower = job_description.lower()
    lines = job_description.split("\n")
    current_section = None

    skill_indicators = [
        "required", "must have", "essential", "minimum", "qualifications",
        "requirements", "what you need", "what we're looking for",
        "you have", "you bring",
    ]
    preferred_indicators = [
        "preferred", "nice to have", "bonus", "plus", "desired",
        "ideally", "it would be great",
    ]
    responsibility_indicators = [
        "responsibilit", "you will", "duties", "what you'll do",
        "role involves", "day to day", "key tasks",
    ]

    for line in lines:
        lower = line.lower().strip()
        if not lower:
            continue

        if any(ind in lower for ind in skill_indicators):
            current_section = "required_skills"
        elif any(ind in lower for ind in preferred_indicators):
            current_section = "preferred_skills"
        elif any(ind in lower for ind in responsibility_indicators):
            current_section = "key_responsibilities"

        if current_section and (
            lower.startswith("-") or lower.startswith("*") or
            lower.startswith("•") or lower.startswith("·") or
            re.match(r"^\d+[\.\)]\s", lower)
        ):
            cleaned = re.sub(r"^[-*•·]\s*", "", lower)
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", cleaned)
            sections[current_section].append(cleaned)

    # Extract multi-word phrases first (higher ATS value)
    for phrase in PHRASE_KEYWORDS:
        if phrase in jd_lower:
            sections["keywords"].append(phrase)

    # Extract single-word tech keywords
    words = re.findall(r"\b[A-Za-z][A-Za-z+#/.]+\b", job_description)
    for word in words:
        if word.lower() in TECH_KEYWORDS and word.lower() not in [k.lower() for k in sections["keywords"]]:
            sections["keywords"].append(word)

    sections["keywords"] = list(dict.fromkeys(sections["keywords"]))

    # Extract experience level
    for pattern, level in EXP_PATTERNS:
        match = re.search(pattern, jd_lower)
        if match:
            sections["experience_level"] = level
            break

    # Extract soft skills (ATS systems increasingly weight these)
    soft_skill_patterns = [
        "communication", "collaboration", "problem.solving", "analytical",
        "detail.oriented", "self.motivated", "team player", "adaptable",
        "creative", "critical thinking", "time management", "organizational",
        "interpersonal", "presentation", "negotiation", "strategic",
        "customer.focused", "results.driven", "fast.paced",
    ]
    for pattern in soft_skill_patterns:
        if re.search(pattern, jd_lower):
            clean = pattern.replace(".", "-")
            sections["soft_skills"].append(clean)

    return sections


def compute_match_score(resume_text: str, job_keywords: dict) -> float:
    """Score how well a resume matches a job description (0-100).

    Weighted scoring: required skills > keywords > preferred > soft skills.
    """
    if not resume_text or not job_keywords:
        return 0.0

    resume_lower = resume_text.lower()
    total_items = 0
    matched_items = 0

    # Required skills — heaviest weight (3x)
    for skill in job_keywords.get("required_skills", []):
        total_items += 3
        skill_words = [w for w in skill.split() if len(w) > 3]
        if skill_words and any(word in resume_lower for word in skill_words):
            matched_items += 3

    # Technical keywords — high weight (2x)
    for keyword in job_keywords.get("keywords", []):
        total_items += 2
        if keyword.lower() in resume_lower:
            matched_items += 2

    # Preferred skills — medium weight (1.5x)
    for skill in job_keywords.get("preferred_skills", []):
        total_items += 1.5
        skill_words = [w for w in skill.split() if len(w) > 3]
        if skill_words and any(word in resume_lower for word in skill_words):
            matched_items += 1.5

    # Soft skills — lower weight (1x)
    for skill in job_keywords.get("soft_skills", []):
        total_items += 1
        clean = skill.replace("-", " ").replace(".", " ")
        if any(w in resume_lower for w in clean.split() if len(w) > 4):
            matched_items += 1

    if total_items == 0:
        return 50.0

    return round((matched_items / total_items) * 100, 1)


def compute_ats_score(tailored_resume: str, job_keywords: dict, job_title: str) -> dict:
    """Compute a dedicated ATS pass-through score with breakdown.

    ATS systems check:
    1. Exact keyword matches (do the words appear?)
    2. Keyword placement (are they in skills section, not buried?)
    3. Job title match (does the resume mention the target role?)
    4. Section headers (are standard headers present?)
    5. Formatting (no special characters that break parsers)
    """
    resume_lower = tailored_resume.lower()
    breakdown = {}

    # 1. Keyword hit rate (40% of ATS score)
    all_keywords = (
        job_keywords.get("keywords", []) +
        [s for s in job_keywords.get("required_skills", []) if len(s.split()) <= 4]
    )
    if all_keywords:
        hits = sum(1 for kw in all_keywords if kw.lower() in resume_lower)
        breakdown["keyword_hit_rate"] = round((hits / len(all_keywords)) * 100)
    else:
        breakdown["keyword_hit_rate"] = 50

    # 2. Skills section density (20% of ATS score)
    skills_section = ""
    skills_match = re.search(
        r"(?:skills|technical skills|core competencies)\s*:?\s*\n(.*?)(?=\n\n|\n[A-Z]|\Z)",
        tailored_resume, re.IGNORECASE | re.DOTALL
    )
    if skills_match:
        skills_section = skills_match.group(1).lower()
    kw_in_skills = sum(1 for kw in job_keywords.get("keywords", []) if kw.lower() in skills_section)
    total_kw = len(job_keywords.get("keywords", [])) or 1
    breakdown["skills_section_density"] = min(100, round((kw_in_skills / total_kw) * 120))

    # 3. Job title match (15% of ATS score)
    title_words = [w.lower() for w in job_title.split() if len(w) > 2]
    title_hits = sum(1 for w in title_words if w in resume_lower)
    breakdown["title_match"] = round((title_hits / max(len(title_words), 1)) * 100)

    # 4. Section headers (15% of ATS score)
    found_headers = 0
    essential_headers = ["experience", "education", "skills"]
    for header in essential_headers:
        if re.search(rf"^{header}", tailored_resume, re.IGNORECASE | re.MULTILINE):
            found_headers += 1
    breakdown["section_headers"] = round((found_headers / len(essential_headers)) * 100)

    # 5. Formatting cleanliness (10% of ATS score)
    format_score = 100
    # Penalize special characters that break ATS parsers
    bad_chars = len(re.findall(r"[│┌┐└┘─═║╔╗╚╝★☆►▪▸▹◆◇●○]", tailored_resume))
    format_score -= min(50, bad_chars * 5)
    # Penalize tables (columns of whitespace)
    table_lines = len(re.findall(r"\t{2,}|  {4,}\S", tailored_resume))
    format_score -= min(30, table_lines * 3)
    breakdown["formatting"] = max(0, format_score)

    # Weighted total
    ats_total = round(
        breakdown["keyword_hit_rate"] * 0.40 +
        breakdown["skills_section_density"] * 0.20 +
        breakdown["title_match"] * 0.15 +
        breakdown["section_headers"] * 0.15 +
        breakdown["formatting"] * 0.10
    )

    return {
        "ats_score": min(100, ats_total),
        "breakdown": breakdown,
    }


def _inject_keywords_into_skills(resume: str, keywords_to_add: list[str]) -> str:
    """Find the skills section and inject missing keywords."""
    if not keywords_to_add:
        return resume

    skills_pattern = re.compile(
        r"((?:skills|technical skills|core competencies|technologies)\s*:?\s*\n)(.*?)(\n\n|\n[A-Z]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = skills_pattern.search(resume)

    if match:
        header = match.group(1)
        existing = match.group(2).strip()
        after = match.group(3)
        # Add missing keywords to the skills line
        additions = ", ".join(keywords_to_add)
        if existing.endswith(","):
            new_skills = f"{existing} {additions}"
        else:
            new_skills = f"{existing}, {additions}"
        return resume[:match.start()] + header + new_skills + "\n" + after + resume[match.end():]
    else:
        # No skills section found — insert one after the summary/objective or at the top
        insert_after = re.search(
            r"((?:summary|objective|profile|about)\s*:?\s*\n.*?)(\n\n)",
            resume, re.IGNORECASE | re.DOTALL,
        )
        skills_block = "\nSkills\n" + ", ".join(keywords_to_add) + "\n"
        if insert_after:
            pos = insert_after.end()
            return resume[:pos] + skills_block + resume[pos:]
        else:
            return skills_block + "\n" + resume

    return resume


def _mirror_job_title_in_summary(resume: str, job_title: str, company_name: str, top_keywords: list[str]) -> str:
    """Rewrite summary/objective to mirror the exact job title (ATS indexes this heavily)."""
    summary_pattern = re.compile(
        r"((?:summary|objective|profile|about)\s*:?\s*\n)(.*?)(?=\n\n|\n[A-Z])",
        re.IGNORECASE | re.DOTALL,
    )
    match = summary_pattern.search(resume)

    kw_str = ", ".join(top_keywords[:6]) if top_keywords else "relevant technologies"

    new_summary = (
        f"Results-driven professional seeking a {job_title} position at {company_name}. "
        f"Proven expertise in {kw_str} with a track record of delivering high-impact solutions. "
        f"Strong collaborator who thrives in fast-paced environments and is passionate about "
        f"building scalable, production-quality systems."
    )

    if match:
        header = match.group(1)
        return resume[:match.start()] + header + new_summary + "\n" + resume[match.end():]
    else:
        return f"Professional Summary\n{new_summary}\n\n{resume}"


def generate_tailored_resume(base_resume: str, job_description: str, job_title: str, company_name: str) -> dict:
    """Generate an ATS-optimized tailored resume.

    The tailoring pipeline:
    1. Extract all keywords, skills, and phrases from the JD
    2. Mirror the exact job title in the summary (ATS indexes title heavily)
    3. Inject missing tech keywords into the skills section
    4. Compute match score and ATS score on the TAILORED version
    5. Return the resume with both scores and actionable notes
    """
    job_keywords = extract_keywords_from_job(job_description)
    resume_lower = base_resume.lower()

    # Identify keywords missing from resume that need injection
    missing_tech = []
    present_tech = []
    for kw in job_keywords.get("keywords", []):
        if kw.lower() in resume_lower:
            present_tech.append(kw)
        else:
            missing_tech.append(kw)

    missing_required = []
    for skill in job_keywords.get("required_skills", []):
        skill_words = [w for w in skill.split() if len(w) > 3]
        if skill_words and not any(w in resume_lower for w in skill_words):
            missing_required.append(skill)

    # Step 1: Mirror job title in summary
    all_kw = present_tech + missing_tech
    tailored = _mirror_job_title_in_summary(base_resume, job_title, company_name, all_kw)

    # Step 2: Inject missing keywords into skills section
    inject_list = missing_tech[:10]  # Don't stuff — ATS detects keyword stuffing
    tailored = _inject_keywords_into_skills(tailored, inject_list)

    # Step 3: Compute scores on the TAILORED resume (not the base)
    match_score = compute_match_score(tailored, job_keywords)
    ats_result = compute_ats_score(tailored, job_keywords, job_title)

    # Build actionable tailoring notes
    tailoring_notes = []
    if missing_required:
        tailoring_notes.append(
            f"ATS flag: These required skills aren't clearly demonstrated in your experience — "
            f"add accomplishments that show them: {'; '.join(missing_required[:5])}"
        )
    if ats_result["breakdown"]["section_headers"] < 100:
        tailoring_notes.append(
            "ATS flag: Use standard section headers — 'Experience', 'Education', 'Skills' — "
            "so ATS parsers can find your content."
        )
    if ats_result["breakdown"]["formatting"] < 80:
        tailoring_notes.append(
            "ATS flag: Special characters or table formatting detected. Use plain text, "
            "standard bullets (- or *), and avoid columns."
        )
    if missing_tech:
        added = inject_list
        still_missing = [k for k in missing_tech if k not in inject_list]
        if added:
            tailoring_notes.append(
                f"Auto-added to Skills section: {', '.join(added)}"
            )
        if still_missing:
            tailoring_notes.append(
                f"Weave these naturally into your experience bullets: {', '.join(still_missing)}"
            )

    return {
        "tailored_resume": tailored,
        "match_score": match_score,
        "ats_score": ats_result["ats_score"],
        "ats_breakdown": ats_result["breakdown"],
        "missing_keywords": missing_tech,
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
    """Generate an ATS-optimized cover letter that mirrors JD keywords.

    ATS systems scan cover letters too — we embed the exact job title,
    required skills, and key phrases from the JD.
    """
    job_keywords = extract_keywords_from_job(job_description)

    # Build keyword-rich strings
    tech_skills = job_keywords.get("keywords", [])[:6]
    required = job_keywords.get("required_skills", [])[:3]
    soft = job_keywords.get("soft_skills", [])[:2]

    skills_str = ", ".join(tech_skills) if tech_skills else "the required technologies"

    # Extract key responsibilities for the body paragraph
    responsibilities = job_keywords.get("key_responsibilities", [])[:3]
    resp_lines = ""
    if responsibilities:
        resp_lines = "".join(
            f"\n- {resp.capitalize()}" for resp in responsibilities
        )

    required_str = ""
    if required:
        clean_required = [r.strip().capitalize() for r in required[:3]]
        required_str = (
            f"\n\nMy background directly addresses your key requirements including "
            f"{', '.join(clean_required)}. "
        )

    soft_str = ""
    if soft:
        clean_soft = [s.replace("-", " ") for s in soft]
        soft_str = f"I bring strong {' and '.join(clean_soft)} skills to complement my technical expertise. "

    return f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company_name}. With hands-on expertise in {skills_str}, I am confident I can contribute meaningfully from day one.
{required_str}
In my previous roles, I have consistently delivered results in areas closely aligned with this position:{resp_lines if resp_lines else '''
- Designing and implementing scalable solutions that drive business outcomes
- Collaborating across teams to ship high-quality products on tight timelines
- Identifying and resolving complex technical challenges proactively'''}

{soft_str}I am drawn to {company_name}'s mission and would welcome the opportunity to discuss how my experience in {skills_str} aligns with your team's goals.

Thank you for your consideration. I look forward to speaking with you.

Best regards,
{candidate_name}
"""
