"""
Self-Discovery Quiz Engine

Maps user interests, skills, work preferences, and values
to ideal job role recommendations. Then searches for matching
real jobs across connected job boards.
"""

QUIZ_QUESTIONS = {
    "interests": {
        "title": "What excites you?",
        "subtitle": "Pick everything that sparks your curiosity",
        "type": "multi",
        "options": [
            {"id": "build", "label": "Building things from scratch", "icon": "hammer"},
            {"id": "analyze", "label": "Analyzing data & finding patterns", "icon": "chart"},
            {"id": "design", "label": "Designing beautiful experiences", "icon": "palette"},
            {"id": "lead", "label": "Leading teams & shaping strategy", "icon": "compass"},
            {"id": "persuade", "label": "Persuading & communicating ideas", "icon": "megaphone"},
            {"id": "solve", "label": "Solving technical puzzles", "icon": "puzzle"},
            {"id": "write", "label": "Writing & storytelling", "icon": "pen"},
            {"id": "optimize", "label": "Organizing & optimizing processes", "icon": "gear"},
            {"id": "numbers", "label": "Working with numbers & finance", "icon": "calculator"},
            {"id": "help", "label": "Helping people learn & grow", "icon": "heart"},
        ],
    },
    "skills": {
        "title": "What are you naturally good at?",
        "subtitle": "Pick your top strengths",
        "type": "multi",
        "options": [
            {"id": "coding", "label": "Programming & coding", "icon": "code"},
            {"id": "visual", "label": "Visual design & aesthetics", "icon": "eye"},
            {"id": "data", "label": "Data analysis & statistics", "icon": "bar-chart"},
            {"id": "communication", "label": "Communication & presenting", "icon": "mic"},
            {"id": "debugging", "label": "Problem solving & debugging", "icon": "bug"},
            {"id": "pm", "label": "Project management & planning", "icon": "calendar"},
            {"id": "content", "label": "Writing & content creation", "icon": "edit"},
            {"id": "sales", "label": "Sales & negotiation", "icon": "handshake"},
            {"id": "leadership", "label": "Leadership & mentoring", "icon": "users"},
            {"id": "research", "label": "Research & learning quickly", "icon": "search"},
        ],
    },
    "workstyle": {
        "title": "How do you like to work?",
        "subtitle": "Pick the option that fits you best",
        "type": "single_each",
        "questions": [
            {
                "id": "team",
                "question": "Team dynamic",
                "options": [
                    {"id": "solo", "label": "Mostly solo / deep focus"},
                    {"id": "small_team", "label": "Small collaborative team"},
                    {"id": "large_team", "label": "Large cross-functional team"},
                ],
            },
            {
                "id": "structure",
                "question": "Work style",
                "options": [
                    {"id": "creative", "label": "Creative & open-ended"},
                    {"id": "balanced", "label": "Mix of creative and structured"},
                    {"id": "structured", "label": "Structured & process-driven"},
                ],
            },
            {
                "id": "pace",
                "question": "Pace",
                "options": [
                    {"id": "fast", "label": "Fast-paced & high energy"},
                    {"id": "moderate", "label": "Steady & sustainable"},
                    {"id": "flexible", "label": "Self-paced & flexible"},
                ],
            },
        ],
    },
    "values": {
        "title": "What matters most in your career?",
        "subtitle": "Pick your top 3 values",
        "type": "multi_limited",
        "max_selections": 3,
        "options": [
            {"id": "salary", "label": "High compensation", "icon": "dollar"},
            {"id": "balance", "label": "Work-life balance", "icon": "scale"},
            {"id": "innovation", "label": "Innovation & creativity", "icon": "lightbulb"},
            {"id": "impact", "label": "Helping others / social impact", "icon": "globe"},
            {"id": "growth", "label": "Career growth & advancement", "icon": "trending-up"},
            {"id": "security", "label": "Job security & stability", "icon": "shield"},
            {"id": "autonomy", "label": "Autonomy & independence", "icon": "flag"},
            {"id": "collaboration", "label": "Team & collaboration", "icon": "people"},
            {"id": "scale", "label": "Impact at massive scale", "icon": "rocket"},
            {"id": "learning", "label": "Continuous learning", "icon": "book"},
        ],
    },
}

ROLE_DATABASE = [
    {
        "role": "Frontend Developer",
        "field": "Software Engineering",
        "search_terms": ["frontend developer", "react developer", "UI developer"],
        "skills_needed": "React, JavaScript, TypeScript, CSS, HTML, UI/UX",
        "signals": {
            "interests": {"build": 3, "design": 2, "solve": 1},
            "skills": {"coding": 3, "visual": 2, "debugging": 1},
            "workstyle": {"team": {"small_team": 2, "solo": 1}, "structure": {"creative": 2, "balanced": 1}},
            "values": {"innovation": 2, "learning": 1, "growth": 1},
        },
    },
    {
        "role": "Backend Developer",
        "field": "Software Engineering",
        "search_terms": ["backend developer", "server engineer", "API developer"],
        "skills_needed": "Python, Java, Node.js, SQL, APIs, Cloud",
        "signals": {
            "interests": {"build": 3, "solve": 3, "optimize": 1},
            "skills": {"coding": 3, "debugging": 2, "data": 1},
            "workstyle": {"team": {"solo": 2, "small_team": 1}, "structure": {"structured": 1, "balanced": 2}},
            "values": {"autonomy": 2, "learning": 1, "scale": 1},
        },
    },
    {
        "role": "Full Stack Developer",
        "field": "Software Engineering",
        "search_terms": ["full stack developer", "fullstack engineer", "web developer"],
        "skills_needed": "React, Node.js, Python, SQL, APIs, Cloud, CSS",
        "signals": {
            "interests": {"build": 3, "solve": 2, "design": 1},
            "skills": {"coding": 3, "debugging": 2, "visual": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"balanced": 2}},
            "values": {"growth": 2, "learning": 1, "autonomy": 1},
        },
    },
    {
        "role": "DevOps Engineer",
        "field": "Software Engineering",
        "search_terms": ["devops engineer", "site reliability engineer", "platform engineer"],
        "skills_needed": "Docker, Kubernetes, AWS, CI/CD, Linux, Terraform",
        "signals": {
            "interests": {"optimize": 3, "solve": 2, "build": 1},
            "skills": {"coding": 2, "debugging": 3, "pm": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"structured": 2}},
            "values": {"security": 2, "scale": 2, "autonomy": 1},
        },
    },
    {
        "role": "Mobile Developer",
        "field": "Software Engineering",
        "search_terms": ["mobile developer", "iOS developer", "android developer", "react native developer"],
        "skills_needed": "Swift, Kotlin, React Native, Flutter, Mobile UI",
        "signals": {
            "interests": {"build": 3, "design": 2},
            "skills": {"coding": 3, "visual": 2},
            "workstyle": {"team": {"small_team": 2}, "structure": {"creative": 1, "balanced": 2}},
            "values": {"innovation": 2, "growth": 1},
        },
    },
    {
        "role": "Data Scientist",
        "field": "Data Science",
        "search_terms": ["data scientist", "machine learning engineer", "AI researcher"],
        "skills_needed": "Python, Machine Learning, Statistics, SQL, TensorFlow, PyTorch",
        "signals": {
            "interests": {"analyze": 3, "solve": 2, "numbers": 1},
            "skills": {"data": 3, "coding": 2, "research": 2},
            "workstyle": {"team": {"solo": 2, "small_team": 1}, "structure": {"creative": 2}},
            "values": {"learning": 3, "innovation": 2, "scale": 1},
        },
    },
    {
        "role": "Data Analyst",
        "field": "Data & Analytics",
        "search_terms": ["data analyst", "business intelligence analyst", "analytics"],
        "skills_needed": "SQL, Excel, Tableau, Python, Statistics, Power BI",
        "signals": {
            "interests": {"analyze": 3, "numbers": 2, "optimize": 1},
            "skills": {"data": 3, "communication": 1, "research": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"structured": 2, "balanced": 1}},
            "values": {"balance": 1, "growth": 1, "security": 1},
        },
    },
    {
        "role": "Data Engineer",
        "field": "Data Engineering",
        "search_terms": ["data engineer", "ETL developer", "data pipeline engineer"],
        "skills_needed": "Python, SQL, Spark, Airflow, AWS, Data Pipelines",
        "signals": {
            "interests": {"build": 2, "analyze": 2, "optimize": 2},
            "skills": {"coding": 3, "data": 2, "debugging": 1},
            "workstyle": {"team": {"solo": 2}, "structure": {"structured": 2}},
            "values": {"salary": 2, "scale": 2, "autonomy": 1},
        },
    },
    {
        "role": "UI/UX Designer",
        "field": "Design",
        "search_terms": ["UX designer", "UI designer", "product designer", "UX researcher"],
        "skills_needed": "Figma, User Research, Wireframing, Prototyping, Design Systems",
        "signals": {
            "interests": {"design": 3, "help": 2, "build": 1},
            "skills": {"visual": 3, "research": 2, "communication": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"creative": 3}},
            "values": {"innovation": 2, "impact": 1, "collaboration": 1},
        },
    },
    {
        "role": "Product Manager",
        "field": "Product Management",
        "search_terms": ["product manager", "product owner", "technical PM"],
        "skills_needed": "Roadmapping, Analytics, User Stories, Stakeholder Management",
        "signals": {
            "interests": {"lead": 3, "analyze": 1, "persuade": 2},
            "skills": {"pm": 3, "communication": 2, "leadership": 2},
            "workstyle": {"team": {"large_team": 2, "small_team": 1}, "structure": {"balanced": 2}},
            "values": {"growth": 2, "scale": 2, "collaboration": 1},
        },
    },
    {
        "role": "Project Manager",
        "field": "Project Management",
        "search_terms": ["project manager", "program manager", "scrum master"],
        "skills_needed": "Agile, Scrum, Jira, Stakeholder Management, Risk Assessment",
        "signals": {
            "interests": {"optimize": 3, "lead": 2},
            "skills": {"pm": 3, "communication": 2, "leadership": 1},
            "workstyle": {"team": {"large_team": 2}, "structure": {"structured": 3}},
            "values": {"security": 2, "collaboration": 2, "balance": 1},
        },
    },
    {
        "role": "Digital Marketing Manager",
        "field": "Marketing",
        "search_terms": ["digital marketing manager", "marketing specialist", "growth marketer"],
        "skills_needed": "SEO, Google Ads, Social Media, Analytics, Content Strategy",
        "signals": {
            "interests": {"persuade": 3, "analyze": 2, "write": 1},
            "skills": {"communication": 2, "data": 2, "content": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"creative": 2}},
            "values": {"growth": 2, "innovation": 1, "salary": 1},
        },
    },
    {
        "role": "Content Writer",
        "field": "Content & Marketing",
        "search_terms": ["content writer", "copywriter", "content strategist"],
        "skills_needed": "Writing, SEO, Content Strategy, Editing, Research",
        "signals": {
            "interests": {"write": 3, "persuade": 2, "help": 1},
            "skills": {"content": 3, "communication": 1, "research": 2},
            "workstyle": {"team": {"solo": 2, "small_team": 1}, "structure": {"creative": 3}},
            "values": {"autonomy": 2, "balance": 2, "innovation": 1},
        },
    },
    {
        "role": "Technical Writer",
        "field": "Technical Writing",
        "search_terms": ["technical writer", "documentation engineer", "API writer"],
        "skills_needed": "Technical Documentation, API Docs, Markdown, Developer Tools",
        "signals": {
            "interests": {"write": 3, "solve": 1, "optimize": 1},
            "skills": {"content": 3, "research": 2, "coding": 1},
            "workstyle": {"team": {"solo": 2}, "structure": {"structured": 2}},
            "values": {"balance": 2, "autonomy": 2, "learning": 1},
        },
    },
    {
        "role": "Sales Representative",
        "field": "Sales",
        "search_terms": ["sales representative", "account executive", "business development"],
        "skills_needed": "CRM, Negotiation, Prospecting, Presentations, Pipeline Management",
        "signals": {
            "interests": {"persuade": 3, "help": 1, "numbers": 1},
            "skills": {"sales": 3, "communication": 2, "leadership": 1},
            "workstyle": {"team": {"small_team": 1, "large_team": 1}, "structure": {"balanced": 1}, "pace": {"fast": 2}},
            "values": {"salary": 3, "growth": 2},
        },
    },
    {
        "role": "Customer Success Manager",
        "field": "Customer Success",
        "search_terms": ["customer success manager", "client success", "account manager"],
        "skills_needed": "Relationship Management, Communication, Analytics, CRM",
        "signals": {
            "interests": {"help": 3, "persuade": 2, "optimize": 1},
            "skills": {"communication": 3, "sales": 1, "pm": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"balanced": 2}},
            "values": {"impact": 2, "collaboration": 2, "balance": 1},
        },
    },
    {
        "role": "Business Analyst",
        "field": "Business & Operations",
        "search_terms": ["business analyst", "systems analyst", "operations analyst"],
        "skills_needed": "SQL, Excel, Requirements Gathering, Process Mapping, Stakeholder Management",
        "signals": {
            "interests": {"analyze": 2, "optimize": 3, "numbers": 1},
            "skills": {"data": 2, "communication": 2, "pm": 1},
            "workstyle": {"team": {"large_team": 1, "small_team": 1}, "structure": {"structured": 2}},
            "values": {"security": 2, "growth": 1, "balance": 1},
        },
    },
    {
        "role": "Financial Analyst",
        "field": "Finance",
        "search_terms": ["financial analyst", "finance manager", "FP&A analyst"],
        "skills_needed": "Financial Modeling, Excel, SQL, Forecasting, Budgeting",
        "signals": {
            "interests": {"numbers": 3, "analyze": 2, "optimize": 1},
            "skills": {"data": 2, "research": 2, "communication": 1},
            "workstyle": {"team": {"solo": 1, "small_team": 1}, "structure": {"structured": 3}},
            "values": {"salary": 2, "security": 2, "growth": 1},
        },
    },
    {
        "role": "HR Recruiter",
        "field": "Human Resources",
        "search_terms": ["recruiter", "talent acquisition", "HR specialist"],
        "skills_needed": "Sourcing, Interviewing, ATS, Employer Branding, Communication",
        "signals": {
            "interests": {"help": 3, "persuade": 2},
            "skills": {"communication": 3, "sales": 1, "research": 1},
            "workstyle": {"team": {"small_team": 1, "large_team": 1}, "structure": {"balanced": 2}},
            "values": {"impact": 2, "collaboration": 2, "balance": 1},
        },
    },
    {
        "role": "Cybersecurity Analyst",
        "field": "Cybersecurity",
        "search_terms": ["cybersecurity analyst", "security engineer", "information security"],
        "skills_needed": "Network Security, SIEM, Penetration Testing, Risk Assessment",
        "signals": {
            "interests": {"solve": 3, "optimize": 2, "analyze": 1},
            "skills": {"debugging": 3, "coding": 1, "research": 2},
            "workstyle": {"team": {"solo": 2, "small_team": 1}, "structure": {"structured": 2}},
            "values": {"security": 3, "salary": 2, "learning": 1},
        },
    },
    {
        "role": "Cloud Architect",
        "field": "Cloud Engineering",
        "search_terms": ["cloud architect", "solutions architect", "cloud engineer"],
        "skills_needed": "AWS, Azure, GCP, Terraform, Networking, Microservices",
        "signals": {
            "interests": {"build": 2, "solve": 2, "optimize": 2},
            "skills": {"coding": 2, "debugging": 2, "research": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"balanced": 2}},
            "values": {"salary": 2, "scale": 2, "autonomy": 1},
        },
    },
    {
        "role": "QA Engineer",
        "field": "Quality Assurance",
        "search_terms": ["QA engineer", "test engineer", "quality assurance", "SDET"],
        "skills_needed": "Test Automation, Selenium, API Testing, CI/CD, Bug Tracking",
        "signals": {
            "interests": {"solve": 2, "optimize": 2, "analyze": 1},
            "skills": {"debugging": 3, "coding": 1, "pm": 1},
            "workstyle": {"team": {"small_team": 2}, "structure": {"structured": 2}},
            "values": {"security": 1, "balance": 2, "learning": 1},
        },
    },
]


def get_quiz_questions():
    """Return all quiz questions for the frontend."""
    return QUIZ_QUESTIONS


def score_roles(answers: dict) -> list[dict]:
    """
    Score all roles based on quiz answers.

    answers format:
    {
        "interests": ["build", "solve", ...],
        "skills": ["coding", "debugging", ...],
        "workstyle": {"team": "solo", "structure": "creative", "pace": "fast"},
        "values": ["salary", "learning", "growth"]
    }
    """
    role_scores = []

    for role in ROLE_DATABASE:
        score = 0
        max_possible = 0
        matched_signals = []

        signals = role["signals"]

        for category in ["interests", "skills"]:
            if category in signals and category in answers:
                user_picks = answers[category]
                for pick_id, weight in signals[category].items():
                    max_possible += weight
                    if pick_id in user_picks:
                        score += weight
                        matched_signals.append(pick_id)

        if "workstyle" in signals and "workstyle" in answers:
            ws_signals = signals["workstyle"]
            ws_answers = answers["workstyle"]
            for ws_dim, ws_weights in ws_signals.items():
                if ws_dim in ws_answers:
                    user_pick = ws_answers[ws_dim]
                    for opt_id, weight in ws_weights.items():
                        max_possible += weight
                        if opt_id == user_pick:
                            score += weight

        if "values" in signals and "values" in answers:
            user_values = answers["values"]
            for val_id, weight in signals["values"].items():
                max_possible += weight
                if val_id in user_values:
                    score += weight

        if max_possible > 0:
            pct = round((score / max_possible) * 100)
        else:
            pct = 0

        role_scores.append({
            "role": role["role"],
            "field": role["field"],
            "match_percent": pct,
            "search_terms": role["search_terms"],
            "skills_needed": role["skills_needed"],
            "matched_signals": matched_signals,
        })

    role_scores.sort(key=lambda x: x["match_percent"], reverse=True)
    return role_scores
