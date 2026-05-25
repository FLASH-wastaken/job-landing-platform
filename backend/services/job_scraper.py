"""
Job Search & Scraping Service
Aggregates job listings from multiple free public APIs and scrapes company career pages.
"""

import httpx
import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus


async def search_remotive(query: str, limit: int = 20) -> list[dict]:
    """Search Remotive API for remote jobs (free, no API key needed)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": query, "limit": limit},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            jobs = []
            for job in data.get("jobs", [])[:limit]:
                jobs.append({
                    "title": job.get("title", ""),
                    "company": job.get("company_name", ""),
                    "location": job.get("candidate_required_location", "Remote"),
                    "url": job.get("url", ""),
                    "description": clean_html(job.get("description", "")),
                    "salary": job.get("salary", ""),
                    "job_type": job.get("job_type", ""),
                    "posted_at": job.get("publication_date", ""),
                    "source": "Remotive",
                    "tags": job.get("tags", []),
                })
            return jobs
    except Exception as e:
        print(f"Remotive search error: {e}")
        return []


async def search_arbeitnow(query: str, limit: int = 20) -> list[dict]:
    """Search Arbeitnow API for jobs (free, no API key needed)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.arbeitnow.com/api/job-board-api",
                params={"search": query, "per_page": limit},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            jobs = []
            for job in data.get("data", [])[:limit]:
                jobs.append({
                    "title": job.get("title", ""),
                    "company": job.get("company_name", ""),
                    "location": job.get("location", ""),
                    "url": job.get("url", ""),
                    "description": clean_html(job.get("description", "")),
                    "salary": "",
                    "job_type": "Remote" if job.get("remote", False) else "On-site",
                    "posted_at": job.get("created_at", ""),
                    "source": "Arbeitnow",
                    "tags": job.get("tags", []),
                })
            return jobs
    except Exception as e:
        print(f"Arbeitnow search error: {e}")
        return []


async def search_himalayas(query: str, limit: int = 20) -> list[dict]:
    """Search Himalayas.app API for jobs (free, no key needed)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://himalayas.app/jobs/api",
                params={"q": query, "limit": limit},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            jobs = []
            for job in data.get("jobs", [])[:limit]:
                salary_str = ""
                if job.get("salaryCurrency") and job.get("salaryMin"):
                    salary_str = f"{job['salaryCurrency']} {job.get('salaryMin', '')} - {job.get('salaryMax', '')}"

                jobs.append({
                    "title": job.get("title", ""),
                    "company": job.get("companyName", ""),
                    "location": job.get("locationRestrictions", ["Remote"]),
                    "url": job.get("applicationLink", "") or f"https://himalayas.app/jobs/{job.get('slug', '')}",
                    "description": job.get("excerpt", "") or job.get("description", ""),
                    "salary": salary_str,
                    "job_type": "Remote" if job.get("categories", []) else "",
                    "posted_at": job.get("pubDate", ""),
                    "source": "Himalayas",
                    "tags": job.get("categories", []),
                })
            return jobs
    except Exception as e:
        print(f"Himalayas search error: {e}")
        return []


async def scrape_career_page(url: str) -> list[dict]:
    """
    Scrape a company career/jobs page for job listings.
    Uses pattern matching to find job-like links on the page.
    """
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code != 200:
                return []

            html = resp.text
            jobs = []

            # Common patterns for job listing links on career pages
            # Look for links containing job-related keywords
            link_pattern = re.compile(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )

            job_keywords = [
                "engineer", "developer", "designer", "manager", "analyst",
                "scientist", "specialist", "coordinator", "director", "lead",
                "architect", "consultant", "associate", "intern", "senior",
                "junior", "staff", "principal", "head of", "vp ",
            ]

            seen_titles = set()
            for match in link_pattern.finditer(html):
                link_url = match.group(1)
                link_text = clean_html(match.group(2)).strip()

                if not link_text or len(link_text) < 5 or len(link_text) > 200:
                    continue

                # Check if link text looks like a job title
                lower_text = link_text.lower()
                if any(kw in lower_text for kw in job_keywords):
                    if link_text not in seen_titles:
                        seen_titles.add(link_text)
                        # Resolve relative URLs
                        if link_url.startswith("/"):
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            link_url = f"{parsed.scheme}://{parsed.netloc}{link_url}"

                        jobs.append({
                            "title": link_text,
                            "company": extract_company_from_url(url),
                            "location": "",
                            "url": link_url,
                            "description": "",
                            "salary": "",
                            "job_type": "",
                            "posted_at": "",
                            "source": f"Career Page: {extract_company_from_url(url)}",
                            "tags": [],
                        })

            return jobs[:30]  # Cap at 30 results
    except Exception as e:
        print(f"Career page scrape error for {url}: {e}")
        return []


def extract_company_from_url(url: str) -> str:
    """Extract company name from URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    # Get the main domain name
    parts = domain.split(".")
    if len(parts) >= 2:
        return parts[0].replace("-", " ").replace("_", " ").title()
    return domain


def clean_html(html_text: str) -> str:
    """Remove HTML tags from text."""
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()[:2000]  # Cap at 2000 chars


async def search_all_sources(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    Search all available job sources concurrently.
    Returns deduplicated, sorted results.
    """
    search_query = query
    if location:
        search_query = f"{query} {location}"

    # Run all searches concurrently
    results = await asyncio.gather(
        search_remotive(search_query, limit),
        search_arbeitnow(search_query, limit),
        search_himalayas(search_query, limit),
        return_exceptions=True,
    )

    all_jobs = []
    for result in results:
        if isinstance(result, list):
            all_jobs.extend(result)

    # Deduplicate by title + company
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = (job["title"].lower().strip(), job["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    return unique_jobs
