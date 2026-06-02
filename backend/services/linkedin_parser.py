"""
LinkedIn Profile Parser

Extracts candidate data from:
1. LinkedIn PDF exports (Save to PDF from linkedin.com)
2. Pasted LinkedIn profile text (copy-paste from the page)

Returns structured candidate data ready to fill the form.
"""

import re
import io


def parse_linkedin_pdf(file_bytes: bytes) -> dict:
    """Parse a LinkedIn profile PDF and extract structured data."""
    import pdfplumber

    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    if not text.strip():
        return {"error": "Could not extract text from PDF"}

    return _parse_profile_text(text)


def parse_linkedin_text(text: str) -> dict:
    """Parse pasted LinkedIn profile text and extract structured data."""
    if not text or len(text.strip()) < 20:
        return {"error": "Text too short to parse"}
    return _parse_profile_text(text)


def _parse_profile_text(text: str) -> dict:
    """Core parser that works on extracted text from any source."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "name": "",
        "email": "",
        "phone": "",
        "field": "",
        "target_role": "",
        "linkedin_url": "",
        "skills": "",
        "years_experience": None,
        "location_preference": "",
        "base_resume_text": text,
    }

    # Extract name (usually the first substantial line)
    for line in lines[:5]:
        # Skip lines that look like headers/navigation
        if any(skip in line.lower() for skip in [
            "linkedin", "contact", "page", "http", "www", "profile",
            "home", "network", "jobs", "messaging",
        ]):
            continue
        # Name is typically 2-4 words, all capitalized or title case
        words = line.split()
        if 1 <= len(words) <= 5 and all(w[0].isupper() for w in words if w.isalpha()):
            result["name"] = line
            break

    # Extract headline/title (usually right after the name)
    name_found = False
    for line in lines:
        if line == result["name"]:
            name_found = True
            continue
        if name_found and line and not line.startswith("http"):
            # This is likely the headline
            if len(line) > 5 and len(line) < 200:
                result["target_role"] = line
                # Try to extract field from headline
                result["field"] = _extract_field(line)
                break

    # Extract LinkedIn URL
    for line in lines:
        url_match = re.search(r"(https?://(?:www\.)?linkedin\.com/in/[^\s]+)", line)
        if url_match:
            result["linkedin_url"] = url_match.group(1)
            break

    # Extract email
    for line in lines:
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", line)
        if email_match:
            result["email"] = email_match.group(0)
            break

    # Extract phone
    for line in lines:
        phone_match = re.search(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}",
            line,
        )
        if phone_match and not re.search(r"\d{4}-\d{4}", phone_match.group(0)):
            result["phone"] = phone_match.group(0)
            break

    # Extract location
    location_patterns = [
        r"(?:based in|located in|location[:\s]+)(.+)",
        r"([\w\s]+,\s*[\w\s]+(?:,\s*[\w\s]+)?)\s*(?:area|region|metro)",
    ]
    for line in lines:
        for pattern in location_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                result["location_preference"] = match.group(1).strip()
                break
        if result["location_preference"]:
            break

    # If no explicit location found, look for city/country patterns near the top
    if not result["location_preference"]:
        for line in lines[:15]:
            # Common LinkedIn location format: "City, State" or "City, Country"
            if re.match(r"^[A-Z][\w\s]+,\s*[A-Z][\w\s]+$", line) and len(line) < 60:
                if line != result["name"] and line != result["target_role"]:
                    result["location_preference"] = line
                    break

    # Extract skills
    skills = _extract_skills(text)
    if skills:
        result["skills"] = ", ".join(skills)

    # Extract years of experience
    result["years_experience"] = _extract_experience_years(text)

    return result


def _extract_field(headline: str) -> str:
    """Infer the professional field from the headline."""
    headline_lower = headline.lower()

    field_map = {
        "software": "Software Engineering",
        "developer": "Software Engineering",
        "engineer": "Software Engineering",
        "frontend": "Software Engineering",
        "backend": "Software Engineering",
        "full stack": "Software Engineering",
        "fullstack": "Software Engineering",
        "devops": "Software Engineering",
        "sre": "Software Engineering",
        "data scien": "Data Science",
        "machine learning": "Data Science",
        "ml engineer": "Data Science",
        "ai ": "Data Science",
        "data analy": "Data & Analytics",
        "business intelligence": "Data & Analytics",
        "data engineer": "Data Engineering",
        "product manage": "Product Management",
        "product owner": "Product Management",
        "project manage": "Project Management",
        "scrum master": "Project Management",
        "design": "Design",
        "ux": "Design",
        "ui": "Design",
        "graphic": "Design",
        "market": "Marketing",
        "growth": "Marketing",
        "seo": "Marketing",
        "content": "Content & Marketing",
        "writer": "Content & Marketing",
        "copywrite": "Content & Marketing",
        "sale": "Sales",
        "business develop": "Sales",
        "account execut": "Sales",
        "customer success": "Customer Success",
        "recruit": "Human Resources",
        "hr ": "Human Resources",
        "human resource": "Human Resources",
        "talent": "Human Resources",
        "financ": "Finance",
        "account": "Finance",
        "consult": "Consulting",
        "secur": "Cybersecurity",
        "cloud": "Cloud Engineering",
        "architect": "Cloud Engineering",
        "qa": "Quality Assurance",
        "test": "Quality Assurance",
        "mobile": "Mobile Development",
        "ios": "Mobile Development",
        "android": "Mobile Development",
    }

    for keyword, field in field_map.items():
        if keyword in headline_lower:
            return field

    return "Technology"


def _extract_skills(text: str) -> list[str]:
    """Extract skills from LinkedIn profile text."""
    skills = []
    text_lower = text.lower()

    # Look for explicit skills section
    skills_section = ""
    skills_start = re.search(
        r"(?:skills|top skills|core competencies|technologies|technical skills)\s*\n",
        text, re.IGNORECASE,
    )
    if skills_start:
        # Take next ~500 chars as skills section
        skills_section = text[skills_start.end():skills_start.end() + 500]

    # Known tech/professional skills to scan for
    known_skills = [
        "Python", "JavaScript", "TypeScript", "React", "Angular", "Vue.js",
        "Node.js", "Java", "C++", "C#", "Go", "Rust", "Swift", "Kotlin",
        "Ruby", "PHP", "Scala", "R", "MATLAB",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
        "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "HTML", "CSS", "Sass", "Tailwind", "Bootstrap",
        "Git", "Linux", "CI/CD", "Jenkins", "GitHub Actions",
        "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
        "TensorFlow", "PyTorch", "Pandas", "NumPy", "Scikit-learn",
        "Agile", "Scrum", "Jira", "Confluence",
        "Figma", "Sketch", "Adobe Creative Suite", "Photoshop",
        "REST API", "GraphQL", "Microservices",
        "Excel", "Power BI", "Tableau", "Google Analytics",
        "Salesforce", "HubSpot",
        "Project Management", "Product Management",
        "Data Analysis", "Data Engineering", "Data Science",
        "Communication", "Leadership", "Team Management",
        "SEO", "Content Strategy", "Digital Marketing",
    ]

    scan_text = skills_section if skills_section else text
    for skill in known_skills:
        if skill.lower() in scan_text.lower():
            skills.append(skill)

    # Also grab bullet-point items from skills section
    if skills_section:
        bullet_skills = re.findall(r"[•\-\*]\s*(.+?)(?:\n|$)", skills_section)
        for bs in bullet_skills:
            clean = bs.strip()
            if 2 < len(clean) < 50 and clean not in skills:
                skills.append(clean)

    return skills[:20]


def _extract_experience_years(text: str) -> int | None:
    """Estimate years of experience from date ranges in the text."""
    # Find year ranges like "2018 - 2024", "2019 - Present"
    current_year = 2026
    date_ranges = re.findall(
        r"(\d{4})\s*[-–—]\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)",
        text,
    )

    if not date_ranges:
        return None

    total_years = 0
    for start_str, end_str in date_ranges:
        start = int(start_str)
        if end_str.isdigit():
            end = int(end_str)
        else:
            end = current_year
        if 1970 < start <= current_year and start <= end:
            total_years += end - start

    return total_years if total_years > 0 else None
