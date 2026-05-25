"""
Job Search & Scraping Service
Aggregates job listings from free public APIs, government job banks worldwide,
and company career pages.

DNS-Resilient: Uses DNS-over-HTTPS (DoH) fallback via Cloudflare (1.1.1.1) and
Google (8.8.8.8) when standard DNS resolution fails. Works on any device/network
without requiring DNS configuration changes.
"""

import httpx
import asyncio
import re
import socket
import html as html_module
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse


# ═══════════════════════════════════════════════════════════════════════════════
# DNS-over-HTTPS Resilience Layer
# ═══════════════════════════════════════════════════════════════════════════════
# Automatically falls back to Cloudflare/Google DoH when local DNS fails.
# This ensures the scraper works on restrictive networks, misconfigured DNS,
# or any device without requiring manual DNS settings.

_doh_cache: dict[str, str] = {}
_orig_getaddrinfo = socket.getaddrinfo
_dns_patched = False


def _install_dns_fallback():
    """Monkey-patch socket.getaddrinfo to use DoH cache as fallback (idempotent)."""
    global _dns_patched
    if _dns_patched:
        return

    def _patched_getaddrinfo(host, port, *args, **kwargs):
        try:
            return _orig_getaddrinfo(host, port, *args, **kwargs)
        except socket.gaierror:
            if host in _doh_cache:
                p = port if isinstance(port, int) else 443
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_doh_cache[host], p))]
            raise

    socket.getaddrinfo = _patched_getaddrinfo
    _dns_patched = True


async def _resolve_via_doh(hostname: str) -> str | None:
    """Resolve hostname using Cloudflare / Google DNS-over-HTTPS."""
    if hostname in _doh_cache:
        return _doh_cache[hostname]

    doh_servers = [
        ("https://1.1.1.1/dns-query", {"name": hostname, "type": "A"}),
        ("https://8.8.8.8/resolve", {"name": hostname, "type": "A"}),
    ]
    for url, params in doh_servers:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(url, params=params, headers={"Accept": "application/dns-json"})
                if r.status_code == 200:
                    for ans in r.json().get("Answer", []):
                        if ans.get("type") == 1:  # A record
                            _doh_cache[hostname] = ans["data"]
                            return ans["data"]
        except Exception:
            continue
    return None


async def _ensure_dns(hostname: str):
    """Pre-resolve hostname; populate DoH cache if standard DNS fails."""
    if not hostname:
        return
    try:
        _orig_getaddrinfo(hostname, 443, socket.AF_INET)
    except socket.gaierror:
        await _resolve_via_doh(hostname)


# ═══════════════════════════════════════════════════════════════════════════════
# Resilient HTTP Client
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


async def resilient_get(url, headers=None, params=None, timeout=20, retries=2):
    """HTTP GET with automatic retries + DNS-over-HTTPS fallback."""
    _install_dns_fallback()
    await _ensure_dns(urlparse(url).hostname)

    h = {
        "User-Agent": _DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        h.update(headers)

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout + attempt * 5, follow_redirects=True) as c:
                return await c.get(url, headers=h, params=params)
        except Exception as e:
            if attempt == retries:
                print(f"[DNS-Resilient] GET {url} failed after {retries+1} attempts: {e}")
            else:
                await asyncio.sleep(0.5 * (attempt + 1))
    return None


async def resilient_post(url, json_data=None, data=None, headers=None, timeout=20, retries=2):
    """HTTP POST with automatic retries + DNS-over-HTTPS fallback."""
    _install_dns_fallback()
    await _ensure_dns(urlparse(url).hostname)

    h = {
        "User-Agent": _DEFAULT_UA,
        "Accept": "application/json,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if json_data is not None:
        h["Content-Type"] = "application/json"
    if headers:
        h.update(headers)

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout + attempt * 5, follow_redirects=True) as c:
                return await c.post(url, json=json_data, data=data, headers=h)
        except Exception as e:
            if attempt == retries:
                print(f"[DNS-Resilient] POST {url} failed after {retries+1} attempts: {e}")
            else:
                await asyncio.sleep(0.5 * (attempt + 1))
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def clean_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = html_module.unescape(clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()[:2000]


def extract_company_from_url(url: str) -> str:
    """Extract company name from URL domain."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    parts = domain.split(".")
    return parts[0].replace("-", " ").replace("_", " ").title() if len(parts) >= 2 else domain


def _job(title, company, location, url, description="", salary="",
         job_type="", posted_at="", source="", tags=None):
    """Build a standardised job dict. Auto-decodes HTML entities in title/company."""
    # Decode any HTML entities (handles double-encoding like &amp;amp;)
    t = html_module.unescape(html_module.unescape(title.strip())) if title else ""
    c = html_module.unescape(html_module.unescape(company.strip())) if company else ""
    loc = location if isinstance(location, str) else ", ".join(location) if location else ""
    loc = html_module.unescape(loc) if loc else ""
    return {
        "title": t,
        "company": c,
        "location": loc,
        "url": url.strip() if url else "",
        "description": description,
        "salary": salary,
        "job_type": job_type,
        "posted_at": posted_at,
        "source": source,
        "tags": tags or [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Free Public Job Board APIs
# ═══════════════════════════════════════════════════════════════════════════════

async def search_remotive(query: str, limit: int = 20) -> list[dict]:
    """Search Remotive API for remote jobs (free, no API key needed)."""
    try:
        resp = await resilient_get(
            "https://remotive.com/api/remote-jobs",
            params={"search": query, "limit": limit},
        )
        if not resp or resp.status_code != 200:
            return []

        data = resp.json()
        jobs = []
        for job in data.get("jobs", [])[:limit]:
            jobs.append(_job(
                title=job.get("title", ""),
                company=job.get("company_name", ""),
                location=job.get("candidate_required_location", "Remote"),
                url=job.get("url", ""),
                description=clean_html(job.get("description", "")),
                salary=job.get("salary", ""),
                job_type=job.get("job_type", ""),
                posted_at=job.get("publication_date", ""),
                source="Remotive",
                tags=job.get("tags", []),
            ))
        return jobs
    except Exception as e:
        print(f"Remotive search error: {e}")
        return []


async def search_arbeitnow(query: str, limit: int = 20) -> list[dict]:
    """Search Arbeitnow API for jobs (free, no API key needed)."""
    try:
        resp = await resilient_get(
            "https://www.arbeitnow.com/api/job-board-api",
            params={"search": query, "per_page": limit},
        )
        if not resp or resp.status_code != 200:
            return []

        data = resp.json()
        jobs = []
        for job in data.get("data", [])[:limit]:
            jobs.append(_job(
                title=job.get("title", ""),
                company=job.get("company_name", ""),
                location=job.get("location", ""),
                url=job.get("url", ""),
                description=clean_html(job.get("description", "")),
                job_type="Remote" if job.get("remote", False) else "On-site",
                posted_at=job.get("created_at", ""),
                source="Arbeitnow",
                tags=job.get("tags", []),
            ))
        return jobs
    except Exception as e:
        print(f"Arbeitnow search error: {e}")
        return []


async def search_himalayas(query: str, limit: int = 20) -> list[dict]:
    """Search Himalayas.app API for jobs (free, no key needed)."""
    try:
        resp = await resilient_get(
            "https://himalayas.app/jobs/api",
            params={"q": query, "limit": limit},
        )
        if not resp or resp.status_code != 200:
            return []

        data = resp.json()
        jobs = []
        for job in data.get("jobs", [])[:limit]:
            salary_str = ""
            if job.get("salaryCurrency") and job.get("salaryMin"):
                salary_str = f"{job['salaryCurrency']} {job.get('salaryMin', '')} - {job.get('salaryMax', '')}"

            loc = job.get("locationRestrictions", ["Remote"])
            jobs.append(_job(
                title=job.get("title", ""),
                company=job.get("companyName", ""),
                location=loc,
                url=job.get("applicationLink", "") or f"https://himalayas.app/jobs/{job.get('slug', '')}",
                description=job.get("excerpt", "") or job.get("description", ""),
                salary=salary_str,
                posted_at=job.get("pubDate", ""),
                source="Himalayas",
                tags=job.get("categories", []),
            ))
        return jobs
    except Exception as e:
        print(f"Himalayas search error: {e}")
        return []


async def search_linkedin_public(query: str, location: str = "", limit: int = 25) -> list[dict]:
    """
    Search LinkedIn public job listings (no API key needed).
    Uses LinkedIn's guest job search endpoint.
    """
    try:
        params = {"keywords": query, "start": 0}
        if location:
            params["location"] = location

        resp = await resilient_get(
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
            params=params,
        )
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        title_pattern = re.compile(
            r'<a[^>]*jobs/view/[^"]*"[^>]*>\s*(.*?)\s*</a>', re.DOTALL | re.IGNORECASE
        )
        company_pattern = re.compile(
            r'<h4[^>]*>\s*<a[^>]*>(.*?)</a>\s*</h4>', re.DOTALL | re.IGNORECASE
        )
        location_pattern = re.compile(
            r'<span[^>]*job-search-card__location[^>]*>(.*?)</span>', re.DOTALL | re.IGNORECASE
        )
        link_pattern = re.compile(
            r'<a[^>]*href="(https://[^"]*linkedin\.com/jobs/view/[^"]*)"', re.IGNORECASE
        )

        titles = [clean_html(t) for t in title_pattern.findall(html)]
        companies = [clean_html(c) for c in company_pattern.findall(html)]
        locations = [clean_html(l) for l in location_pattern.findall(html)]
        links = link_pattern.findall(html)

        clean_links = []
        for link in links:
            clean_url = link.split("?")[0]
            if clean_url not in clean_links:
                clean_links.append(clean_url)

        count = min(len(titles), len(companies), limit)
        jobs = []
        for i in range(count):
            jobs.append(_job(
                title=titles[i],
                company=companies[i] if i < len(companies) else "",
                location=locations[i] if i < len(locations) else "",
                url=clean_links[i] if i < len(clean_links) else "",
                source="LinkedIn",
            ))
        return jobs[:limit]
    except Exception as e:
        print(f"LinkedIn search error: {e}")
        return []


async def search_indeed(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """Search Indeed for jobs (bot detection may return 403)."""
    try:
        domain = "www.indeed.com"
        loc_lower = (location or "").lower()
        if any(kw in loc_lower for kw in ["india", "mumbai", "bangalore", "bengaluru", "delhi", "pune", "hyderabad", "chennai"]):
            domain = "in.indeed.com"
        elif any(kw in loc_lower for kw in ["uk", "london", "england"]):
            domain = "uk.indeed.com"
        elif any(kw in loc_lower for kw in ["canada", "toronto", "vancouver"]):
            domain = "ca.indeed.com"

        params = {"q": query, "fromage": "30", "limit": str(limit)}
        if location:
            params["l"] = location

        resp = await resilient_get(f"https://{domain}/jobs", params=params)
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        title_pattern = re.compile(
            r'<h2[^>]*jobTitle[^>]*>.*?<span[^>]*>(.*?)</span>', re.DOTALL | re.IGNORECASE
        )
        company_pattern = re.compile(
            r'data-testid="company-name"[^>]*>(.*?)<', re.DOTALL | re.IGNORECASE
        )
        location_pattern = re.compile(
            r'data-testid="text-location"[^>]*>(.*?)<', re.DOTALL | re.IGNORECASE
        )

        titles = [clean_html(t) for t in title_pattern.findall(html)]
        companies = [clean_html(c) for c in company_pattern.findall(html)]
        locations_found = [clean_html(l) for l in location_pattern.findall(html)]

        jobs = []
        for i in range(min(len(titles), limit)):
            jobs.append(_job(
                title=titles[i],
                company=companies[i] if i < len(companies) else "",
                location=locations_found[i] if i < len(locations_found) else location,
                url=f"https://{domain}/jobs?q={quote_plus(titles[i])}",
                source="Indeed",
            ))
        return jobs
    except Exception as e:
        print(f"Indeed search error: {e}")
        return []


async def search_glassdoor(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """Search Glassdoor for jobs (bot detection may return 403)."""
    try:
        loc_lower = (location or "").lower()
        base = "https://www.glassdoor.co.in" if any(
            kw in loc_lower for kw in ["india", "mumbai", "bangalore", "delhi", "pune"]
        ) else "https://www.glassdoor.com"

        params = {"sc.keyword": query}
        if location:
            params["locKeyword"] = location

        resp = await resilient_get(f"{base}/Job/jobs.htm", params=params)
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        title_pattern = re.compile(
            r'<a[^>]*data-test="job-link"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE
        )
        title_fallback = re.compile(
            r'class="[^"]*JobCard[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE
        )
        company_pattern = re.compile(
            r'class="[^"]*EmployerProfile[^"]*"[^>]*>(.*?)<', re.DOTALL | re.IGNORECASE
        )

        titles = [clean_html(t) for t in title_pattern.findall(html)]
        if not titles:
            titles = [clean_html(t) for t in title_fallback.findall(html)]
        companies = [clean_html(c) for c in company_pattern.findall(html)]

        jobs = []
        for i in range(min(len(titles), limit)):
            jobs.append(_job(
                title=titles[i],
                company=companies[i] if i < len(companies) else "",
                location=location,
                url="",
                source="Glassdoor",
            ))
        return jobs
    except Exception as e:
        print(f"Glassdoor search error: {e}")
        return []


async def search_jobicy(query: str, limit: int = 15) -> list[dict]:
    """Search Jobicy API for remote jobs (free, no key needed)."""
    try:
        resp = await resilient_get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": limit, "tag": query.split()[0].lower()},
        )
        if not resp or resp.status_code != 200:
            return []

        data = resp.json()
        jobs = []
        for job in data.get("jobs", [])[:limit]:
            salary = ""
            if job.get("annualSalaryMin"):
                salary = f"${job['annualSalaryMin']:,} - ${job.get('annualSalaryMax', 0):,}"

            jobs.append(_job(
                title=job.get("jobTitle", ""),
                company=job.get("companyName", ""),
                location=job.get("jobGeo", "Remote"),
                url=job.get("url", ""),
                description=clean_html(job.get("jobDescription", ""))[:500],
                salary=salary,
                job_type=job.get("jobType", ""),
                posted_at=job.get("pubDate", ""),
                source="Jobicy",
                tags=[job.get("jobIndustry", "")] if job.get("jobIndustry") else [],
            ))
        return jobs
    except Exception as e:
        print(f"Jobicy search error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Government Job Banks — Worldwide
# ═══════════════════════════════════════════════════════════════════════════════

async def search_singapore_mcf(query: str, limit: int = 15) -> list[dict]:
    """
    Singapore — MyCareersFuture.gov.sg
    Public REST API, no authentication needed.
    Operated by Workforce Singapore (WSG), a statutory board under the Ministry of Manpower.
    """
    try:
        resp = await resilient_get(
            "https://api.mycareersfuture.gov.sg/v2/jobs",
            params={
                "search": query,
                "limit": limit,
                "page": 0,
                "sortBy": "new_posting_date",
            },
            headers={"Accept": "application/json"},
        )
        if not resp or resp.status_code != 200:
            return []

        data = resp.json()
        results = data.get("results", [])
        jobs = []
        for item in results[:limit]:
            title = item.get("title", "")
            company = ""
            co = item.get("postedCompany", {})
            if isinstance(co, dict):
                company = co.get("name", "")
            elif isinstance(co, str):
                company = co

            salary = ""
            sal = item.get("salary", {})
            if isinstance(sal, dict):
                mn = sal.get("minimum", {})
                mx = sal.get("maximum", {})
                if isinstance(mn, dict) and mn.get("amount"):
                    salary = f"SGD {mn['amount']:,.0f}"
                    if isinstance(mx, dict) and mx.get("amount"):
                        salary += f" - {mx['amount']:,.0f}"
                elif isinstance(mn, (int, float)) and mn:
                    salary = f"SGD {mn:,.0f}"
                    if isinstance(mx, (int, float)) and mx:
                        salary += f" - {mx:,.0f}"

            uuid = item.get("uuid", "")
            url = f"https://www.mycareersfuture.gov.sg/job/{uuid}" if uuid else ""

            jobs.append(_job(
                title=title,
                company=company,
                location="Singapore",
                url=url,
                description=clean_html(item.get("description", ""))[:500],
                salary=salary,
                job_type=item.get("employmentType", ""),
                posted_at=item.get("metadata", {}).get("newPostingDate", "") if isinstance(item.get("metadata"), dict) else "",
                source="Gov: MyCareersFuture.sg",
                tags=item.get("categories", []) if isinstance(item.get("categories"), list) else [],
            ))
        return jobs
    except Exception as e:
        print(f"Singapore MCF error: {e}")
        return []


async def search_canada_jobbank(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    Canada — Job Bank (jobbank.gc.ca)
    Government of Canada's official job search portal.
    Scrapes HTML search results from <article> elements.
    """
    try:
        params = {"searchstring": query, "sort": "D"}
        if location:
            params["locationstring"] = location

        resp = await resilient_get(
            "https://www.jobbank.gc.ca/jobsearch/jobsearch",
            params=params,
        )
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        jobs = []

        # Canada Job Bank structure:
        # <article> contains each job card
        #   <span class="noctitle">actual job title</span>
        #   <li class="business">company name</li>
        #   <li class="location">Location City (Province)</li>
        #   <li class="salary">Salary $XX.XX hourly/annually</li>
        #   <a href="/jobsearch/jobposting/ID">...</a>
        article_pattern = re.compile(
            r'<article[^>]*>(.*?)</article>', re.DOTALL | re.IGNORECASE
        )
        articles = article_pattern.findall(html)

        for art in articles[:limit]:
            # Extract title from noctitle span
            title_match = re.search(
                r'<span[^>]*class="[^"]*noctitle[^"]*"[^>]*>(.*?)</span>',
                art, re.DOTALL | re.IGNORECASE,
            )
            # Extract company
            company_match = re.search(
                r'<li[^>]*class="[^"]*business[^"]*"[^>]*>(.*?)</li>',
                art, re.DOTALL | re.IGNORECASE,
            )
            # Extract location (strip "Location" prefix)
            location_match = re.search(
                r'<li[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</li>',
                art, re.DOTALL | re.IGNORECASE,
            )
            # Extract salary (strip "Salary" prefix)
            salary_match = re.search(
                r'<li[^>]*class="[^"]*salary[^"]*"[^>]*>(.*?)</li>',
                art, re.DOTALL | re.IGNORECASE,
            )
            # Extract URL
            url_match = re.search(
                r'href="(/jobsearch/jobposting/\d+)', art, re.IGNORECASE
            )

            title = clean_html(title_match.group(1)) if title_match else ""
            if not title or len(title) < 3:
                continue

            company = clean_html(company_match.group(1)) if company_match else ""
            loc = clean_html(location_match.group(1)) if location_match else "Canada"
            loc = re.sub(r'^Location\s*', '', loc)  # Strip "Location" prefix
            salary = clean_html(salary_match.group(1)) if salary_match else ""
            salary = re.sub(r'^Salary\s*', '', salary)  # Strip "Salary" prefix
            job_url = f"https://www.jobbank.gc.ca{url_match.group(1)}" if url_match else ""

            jobs.append(_job(
                title=title.title(),  # Capitalize title
                company=company,
                location=loc,
                url=job_url,
                salary=salary,
                source="Gov: Canada Job Bank",
            ))

        return jobs[:limit]
    except Exception as e:
        print(f"Canada Job Bank error: {e}")
        return []


async def search_eures(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    European Union — EURES (ec.europa.eu/eures)
    EU-wide job mobility portal covering all 27 member states + EEA.
    Attempts the JVSE (Job Vacancy Search Engine) API.
    """
    try:
        # EURES has a search API endpoint
        search_body = {
            "keywords": [{"keyword": query}],
            "resultsPerPage": limit,
            "pageNumber": 1,
        }
        if location:
            search_body["locationCodes"] = [location]

        resp = await resilient_post(
            "https://ec.europa.eu/eures/eures-searchengine/page/jv-search/search",
            json_data=search_body,
            headers={"Accept": "application/json", "Origin": "https://eures.ec.europa.eu"},
        )

        if not resp or resp.status_code != 200:
            # Fallback: try the simpler EURES search page
            resp = await resilient_get(
                "https://ec.europa.eu/eures/portal/jms",
                params={"keywords": query, "page": "1", "resultsPerPage": str(limit)},
            )
            if not resp or resp.status_code != 200:
                return []

            # Try parsing HTML
            html = resp.text
            title_pattern = re.compile(
                r'class="[^"]*job-title[^"]*"[^>]*>(.*?)<', re.DOTALL | re.IGNORECASE
            )
            company_pattern = re.compile(
                r'class="[^"]*company[^"]*"[^>]*>(.*?)<', re.DOTALL | re.IGNORECASE
            )
            location_pattern = re.compile(
                r'class="[^"]*location[^"]*"[^>]*>(.*?)<', re.DOTALL | re.IGNORECASE
            )

            titles = [clean_html(t) for t in title_pattern.findall(html)]
            companies = [clean_html(c) for c in company_pattern.findall(html)]
            locations_found = [clean_html(l) for l in location_pattern.findall(html)]

            jobs = []
            for i in range(min(len(titles), limit)):
                jobs.append(_job(
                    title=titles[i],
                    company=companies[i] if i < len(companies) else "",
                    location=locations_found[i] if i < len(locations_found) else "Europe",
                    url="https://eures.ec.europa.eu",
                    source="Gov: EURES (EU)",
                ))
            return jobs

        # Parse JSON API response
        data = resp.json()
        results = data.get("jvs", data.get("results", data.get("data", [])))
        if isinstance(results, dict):
            results = results.get("resultList", results.get("items", []))

        jobs = []
        for item in (results if isinstance(results, list) else [])[:limit]:
            title = item.get("title", item.get("jobTitle", ""))
            company = item.get("company", item.get("employerName", ""))
            loc = item.get("location", item.get("locationName", "Europe"))
            url = item.get("url", item.get("applicationUrl", ""))

            if isinstance(loc, dict):
                loc = loc.get("name", loc.get("city", "Europe"))
            elif isinstance(loc, list):
                loc = ", ".join(loc) if loc else "Europe"

            jobs.append(_job(
                title=clean_html(str(title)),
                company=clean_html(str(company)),
                location=str(loc),
                url=str(url) if url else "https://eures.ec.europa.eu",
                source="Gov: EURES (EU)",
            ))
        return jobs
    except Exception as e:
        print(f"EURES search error: {e}")
        return []


async def search_uk_findajob(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    United Kingdom — Find a Job (findajob.dwp.gov.uk)
    Department for Work and Pensions official job search portal.
    """
    try:
        params = {"q": query, "pp": str(limit), "sort": "dt.rv.di"}
        if location:
            params["w"] = location

        resp = await resilient_get(
            "https://findajob.dwp.gov.uk/search",
            params=params,
        )
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        jobs = []

        # Find a Job uses structured HTML with job cards
        title_pattern = re.compile(
            r'<a[^>]*href="(/job/[^"]*)"[^>]*class="[^"]*govuk-link[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        # Fallback: any link to /job/ pages
        title_fallback = re.compile(
            r'<a[^>]*href="(/job/\d+/[^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        company_pattern = re.compile(
            r'<p[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )
        location_pattern = re.compile(
            r'<p[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )
        salary_pattern = re.compile(
            r'<p[^>]*class="[^"]*salary[^"]*"[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )

        matches = title_pattern.findall(html)
        if not matches:
            matches = title_fallback.findall(html)

        companies = [clean_html(c) for c in company_pattern.findall(html)]
        locations_found = [clean_html(l) for l in location_pattern.findall(html)]
        salaries = [clean_html(s) for s in salary_pattern.findall(html)]

        for i, (path, title_html) in enumerate(matches[:limit]):
            title = clean_html(title_html)
            if not title or len(title) < 3:
                continue

            jobs.append(_job(
                title=title,
                company=companies[i] if i < len(companies) else "",
                location=locations_found[i] if i < len(locations_found) else "United Kingdom",
                url=f"https://findajob.dwp.gov.uk{path}",
                salary=salaries[i] if i < len(salaries) else "",
                source="Gov: UK Find a Job",
            ))

        return jobs[:limit]
    except Exception as e:
        print(f"UK Find a Job error: {e}")
        return []


async def search_india_ncs(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    India — National Career Service (ncs.gov.in)
    Ministry of Labour & Employment, Government of India.
    """
    try:
        # NCS has a search API endpoint
        params = {"keyword": query, "pageNo": "1", "pageSize": str(limit)}
        if location:
            params["location"] = location

        # Try their API endpoint first
        resp = await resilient_post(
            "https://www.ncs.gov.in/api/job/search",
            json_data={"keyword": query, "location": location or "", "page": 1, "size": limit},
        )

        if not resp or resp.status_code != 200:
            # Fallback: try the search page
            resp = await resilient_get(
                "https://www.ncs.gov.in/content-repository/Pages/SearchJobs.aspx",
                params={"Keyword": query},
            )
            if not resp or resp.status_code != 200:
                return []

            # Parse HTML
            html = resp.text
            title_pattern = re.compile(
                r'<a[^>]*class="[^"]*job-title[^"]*"[^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE,
            )
            title_fallback = re.compile(
                r'<h[34][^>]*>.*?<a[^>]*href="[^"]*"[^>]*>(.*?)</a>.*?</h[34]>',
                re.DOTALL | re.IGNORECASE,
            )
            company_pattern = re.compile(
                r'<span[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</span>',
                re.DOTALL | re.IGNORECASE,
            )
            location_pattern = re.compile(
                r'<span[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</span>',
                re.DOTALL | re.IGNORECASE,
            )

            titles = [clean_html(t) for t in title_pattern.findall(html)]
            if not titles:
                titles = [clean_html(t) for t in title_fallback.findall(html)]
            companies = [clean_html(c) for c in company_pattern.findall(html)]
            locations_found = [clean_html(l) for l in location_pattern.findall(html)]

            jobs = []
            for i in range(min(len(titles), limit)):
                jobs.append(_job(
                    title=titles[i],
                    company=companies[i] if i < len(companies) else "",
                    location=locations_found[i] if i < len(locations_found) else "India",
                    url="https://www.ncs.gov.in",
                    source="Gov: India NCS",
                ))
            return jobs

        # Parse JSON API response
        data = resp.json()
        results = data.get("data", data.get("jobs", data.get("results", [])))
        if not isinstance(results, list):
            results = []

        jobs = []
        for item in results[:limit]:
            jobs.append(_job(
                title=item.get("title", item.get("jobTitle", "")),
                company=item.get("company", item.get("organizationName", "")),
                location=item.get("location", item.get("city", "India")),
                url=item.get("url", item.get("applyUrl", "https://www.ncs.gov.in")),
                salary=item.get("salary", ""),
                source="Gov: India NCS",
            ))
        return jobs
    except Exception as e:
        print(f"India NCS error: {e}")
        return []


async def search_australia_jobsearch(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    Australia — Australian Government Job Search (jobsearch.gov.au)
    Department of Employment and Workplace Relations.
    """
    try:
        params = {"keywords": query, "pageSize": str(limit), "page": "1"}
        if location:
            params["suburb"] = location

        resp = await resilient_get(
            "https://jobsearch.gov.au/api/job",
            params=params,
            headers={"Accept": "application/json"},
        )

        if not resp or resp.status_code != 200:
            # Fallback: try HTML page
            resp = await resilient_get(
                "https://jobsearch.gov.au/job/search",
                params={"keywords": query},
            )
            if not resp or resp.status_code != 200:
                return []

            html = resp.text
            title_pattern = re.compile(
                r'<a[^>]*href="(/job/[^"]*)"[^>]*>(.*?)</a>',
                re.DOTALL | re.IGNORECASE,
            )
            company_pattern = re.compile(
                r'<span[^>]*class="[^"]*employer[^"]*"[^>]*>(.*?)</span>',
                re.DOTALL | re.IGNORECASE,
            )
            location_pattern = re.compile(
                r'<span[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</span>',
                re.DOTALL | re.IGNORECASE,
            )

            matches = title_pattern.findall(html)
            companies = [clean_html(c) for c in company_pattern.findall(html)]
            locations_found = [clean_html(l) for l in location_pattern.findall(html)]

            jobs = []
            for i, (path, title_html) in enumerate(matches[:limit]):
                title = clean_html(title_html)
                if title and len(title) > 3:
                    jobs.append(_job(
                        title=title,
                        company=companies[i] if i < len(companies) else "",
                        location=locations_found[i] if i < len(locations_found) else "Australia",
                        url=f"https://jobsearch.gov.au{path}",
                        source="Gov: Australia JobSearch",
                    ))
            return jobs

        # Parse JSON API
        data = resp.json()
        results = data.get("jobs", data.get("data", data.get("results", [])))
        if not isinstance(results, list):
            return []

        jobs = []
        for item in results[:limit]:
            jobs.append(_job(
                title=item.get("title", item.get("jobTitle", "")),
                company=item.get("employer", item.get("company", "")),
                location=item.get("location", item.get("suburb", "Australia")),
                url=item.get("url", item.get("detailUrl", "")),
                salary=item.get("salary", ""),
                posted_at=item.get("postedDate", ""),
                source="Gov: Australia JobSearch",
            ))
        return jobs
    except Exception as e:
        print(f"Australia JobSearch error: {e}")
        return []


async def search_newzealand_jobs(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    New Zealand — jobs.govt.nz
    New Zealand Government job portal.
    """
    try:
        params = {"query": query, "page": "1"}
        if location:
            params["region"] = location

        resp = await resilient_get(
            "https://jobs.govt.nz/search",
            params=params,
        )
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        title_pattern = re.compile(
            r'<a[^>]*href="(/job/[^"]*)"[^>]*class="[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        title_fallback = re.compile(
            r'<h[23][^>]*class="[^"]*job[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        company_pattern = re.compile(
            r'<(?:span|div)[^>]*class="[^"]*(?:org|agency|employer)[^"]*"[^>]*>(.*?)</(?:span|div)>',
            re.DOTALL | re.IGNORECASE,
        )
        location_pattern = re.compile(
            r'<(?:span|div)[^>]*class="[^"]*(?:location|region)[^"]*"[^>]*>(.*?)</(?:span|div)>',
            re.DOTALL | re.IGNORECASE,
        )

        matches = title_pattern.findall(html)
        if not matches:
            titles_raw = title_fallback.findall(html)
            matches = [(f"/job/{i}", t) for i, t in enumerate(titles_raw)]

        companies = [clean_html(c) for c in company_pattern.findall(html)]
        locations_found = [clean_html(l) for l in location_pattern.findall(html)]

        jobs = []
        for i, (path, title_html) in enumerate(matches[:limit]):
            title = clean_html(title_html)
            if title and len(title) > 3:
                jobs.append(_job(
                    title=title,
                    company=companies[i] if i < len(companies) else "",
                    location=locations_found[i] if i < len(locations_found) else "New Zealand",
                    url=f"https://jobs.govt.nz{path}" if path.startswith("/") else "",
                    source="Gov: New Zealand",
                ))
        return jobs[:limit]
    except Exception as e:
        print(f"New Zealand jobs error: {e}")
        return []


async def search_eu_careers(query: str, limit: int = 10) -> list[dict]:
    """
    European Union — EU Careers (EPSO)
    European Personnel Selection Office — jobs at EU institutions.
    Searches the EPSO job opportunities page.
    """
    try:
        resp = await resilient_get(
            "https://epso.europa.eu/en/job-opportunities",
            params={"search": query},
        )
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        # Look for actual job/competition links with specific titles
        title_pattern = re.compile(
            r'<a[^>]*href="(/en/job-opportunities/[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        # Generic nav links to filter out
        generic_terms = [
            "apply for a", "ongoing competitions", "successful candidates",
            "reserve lists", "traineeship", "how to apply", "selection procedure",
            "read more", "learn more", "see all", "view all", "back to",
        ]

        matches = title_pattern.findall(html)
        jobs = []
        for path, title_html in matches[:limit * 2]:
            title = clean_html(title_html)
            if not title or len(title) < 5:
                continue
            # Skip generic navigation links
            if any(g in title.lower() for g in generic_terms):
                continue
            jobs.append(_job(
                title=title,
                company="European Union",
                location="Brussels / Luxembourg / EU",
                url=f"https://epso.europa.eu{path}" if path.startswith("/") else "https://epso.europa.eu",
                source="Gov: EU Careers (EPSO)",
            ))

        return jobs[:limit]
    except Exception as e:
        print(f"EU Careers error: {e}")
        return []


async def search_un_careers(query: str, limit: int = 10) -> list[dict]:
    """
    United Nations — UN Careers (careers.un.org)
    International organization jobs portal.
    """
    try:
        resp = await resilient_get(
            "https://careers.un.org/jobSearchDescription",
            params={"keyword": query, "department": "", "location": ""},
        )
        if not resp or resp.status_code != 200:
            # Try alternate URL
            resp = await resilient_get(
                "https://careers.un.org/lbw/home.aspx",
                params={"viewtype": "SJ", "query": query},
            )
            if not resp or resp.status_code != 200:
                return []

        html = resp.text
        # UN Careers uses various patterns for job listings
        title_pattern = re.compile(
            r'<a[^>]*href="([^"]*(?:job|position|vacancy)[^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        title_fallback = re.compile(
            r'<td[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</td>',
            re.DOTALL | re.IGNORECASE,
        )
        location_pattern = re.compile(
            r'<td[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</td>',
            re.DOTALL | re.IGNORECASE,
        )

        matches = title_pattern.findall(html)
        if not matches:
            titles_raw = title_fallback.findall(html)
            matches = [("", t) for t in titles_raw]

        locations_found = [clean_html(l) for l in location_pattern.findall(html)]

        jobs = []
        for i, (url_path, title_html) in enumerate(matches[:limit]):
            title = clean_html(title_html)
            if title and len(title) > 3 and "cookie" not in title.lower():
                job_url = url_path if url_path.startswith("http") else (
                    f"https://careers.un.org{url_path}" if url_path.startswith("/") else "https://careers.un.org"
                )
                jobs.append(_job(
                    title=title,
                    company="United Nations",
                    location=locations_found[i] if i < len(locations_found) else "International",
                    url=job_url,
                    source="Gov: UN Careers",
                ))
        return jobs
    except Exception as e:
        print(f"UN Careers error: {e}")
        return []


async def search_worldbank_jobs(query: str, limit: int = 10) -> list[dict]:
    """
    World Bank Group — Jobs (worldbankgroup.csod.com)
    International development organization job portal.
    """
    try:
        # World Bank uses Cornerstone OnDemand for recruitment
        resp = await resilient_get(
            "https://worldbankgroup.csod.com/ats/careersite/search.aspx",
            params={"site": "1", "c": "worldbankgroup", "query": query},
        )
        if not resp or resp.status_code != 200:
            # Fallback to main careers page
            resp = await resilient_get(
                "https://www.worldbank.org/en/about/careers",
                params={"q": query},
            )
            if not resp or resp.status_code != 200:
                return []

        html = resp.text

        # Look for job title links
        title_pattern = re.compile(
            r'<a[^>]*href="([^"]*)"[^>]*class="[^"]*(?:job|posting|title)[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        title_fallback = re.compile(
            r'<a[^>]*href="([^"]*(?:requisition|job|posting)[^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )
        location_pattern = re.compile(
            r'<(?:span|div|td)[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</(?:span|div|td)>',
            re.DOTALL | re.IGNORECASE,
        )

        matches = title_pattern.findall(html)
        if not matches:
            matches = title_fallback.findall(html)
        locations_found = [clean_html(l) for l in location_pattern.findall(html)]

        # Filter out navigation/generic links
        generic = ["home", "search", "sign in", "register", "log in", "privacy", "terms"]
        jobs = []
        for i, (url_path, title_html) in enumerate(matches[:limit * 2]):
            title = clean_html(title_html)
            if not title or len(title) < 5 or any(g in title.lower() for g in generic):
                continue
            job_url = url_path if url_path.startswith("http") else (
                f"https://worldbankgroup.csod.com{url_path}" if url_path.startswith("/") else
                "https://www.worldbank.org/en/about/careers"
            )
            jobs.append(_job(
                title=title,
                company="World Bank Group",
                location=locations_found[i] if i < len(locations_found) else "Washington DC / Global",
                url=job_url,
                source="Gov: World Bank",
            ))

        return jobs[:limit]
    except Exception as e:
        print(f"World Bank jobs error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Career Page Scraper
# ═══════════════════════════════════════════════════════════════════════════════

async def scrape_career_page(url: str) -> list[dict]:
    """
    Scrape a company career/jobs page for job listings.
    Uses pattern matching to find job-like links on the page.
    """
    try:
        resp = await resilient_get(url)
        if not resp or resp.status_code != 200:
            return []

        html = resp.text
        jobs = []

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

            lower_text = link_text.lower()
            if any(kw in lower_text for kw in job_keywords):
                if link_text not in seen_titles:
                    seen_titles.add(link_text)
                    if link_url.startswith("/"):
                        parsed = urlparse(url)
                        link_url = f"{parsed.scheme}://{parsed.netloc}{link_url}"

                    jobs.append(_job(
                        title=link_text,
                        company=extract_company_from_url(url),
                        location="",
                        url=link_url,
                        source=f"Career Page: {extract_company_from_url(url)}",
                    ))

        return jobs[:30]
    except Exception as e:
        print(f"Career page scrape error for {url}: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Aggregated Search — All Sources
# ═══════════════════════════════════════════════════════════════════════════════

async def search_all_sources(query: str, location: str = "", limit: int = 15) -> list[dict]:
    """
    Search ALL available job sources concurrently (13 sources):
    - 7 public job boards (Remotive, Arbeitnow, Himalayas, LinkedIn, Indeed, Glassdoor, Jobicy)
    - 6+ government job banks (Singapore, Canada, EU/EURES, UK, India, Australia, NZ, UN, World Bank)

    Returns deduplicated, relevance-sorted results.
    All sources are DNS-resilient via DoH fallback.
    """
    search_query = f"{query} {location}".strip() if location else query

    # Run ALL sources concurrently — failed sources return []
    results = await asyncio.gather(
        # ─── Public Job Boards ───
        search_remotive(search_query, limit),
        search_arbeitnow(search_query, limit),
        search_himalayas(search_query, limit),
        search_linkedin_public(query, location, limit),
        search_indeed(query, location, limit),
        search_glassdoor(query, location, limit),
        search_jobicy(query, limit),
        # ─── Government Job Banks ───
        search_singapore_mcf(query, limit),
        search_canada_jobbank(query, location, limit),
        search_eures(query, location, limit),
        search_uk_findajob(query, location, limit),
        search_india_ncs(query, location, limit),
        search_australia_jobsearch(query, location, limit),
        search_newzealand_jobs(query, location, limit),
        search_eu_careers(query, limit // 2),
        search_un_careers(query, limit // 2),
        search_worldbank_jobs(query, limit // 2),
        return_exceptions=True,
    )

    all_jobs = []
    source_counts = {}
    for result in results:
        if isinstance(result, list):
            for job in result:
                src = job.get("source", "Unknown")
                source_counts[src] = source_counts.get(src, 0) + 1
            all_jobs.extend(result)

    # Log source breakdown
    if source_counts:
        breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(source_counts.items()))
        print(f"[Job Search] Sources: {breakdown} | Total raw: {len(all_jobs)}")

    # Deduplicate by title + company (case-insensitive)
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        key = (job["title"].lower().strip(), job["company"].lower().strip())
        if key not in seen and job["title"]:  # Skip empty titles
            seen.add(key)
            unique_jobs.append(job)

    # Sort: prioritize jobs matching the location filter
    if location:
        loc_lower = location.lower()

        def relevance_score(job):
            score = 0
            job_loc = job.get("location", "")
            if isinstance(job_loc, list):
                job_loc = ", ".join(job_loc)
            job_loc_lower = job_loc.lower()

            # Location match gets highest priority
            if loc_lower in job_loc_lower:
                score += 100
            # Government sources get a boost (more reliable)
            if "Gov:" in job.get("source", ""):
                score += 30
            # LinkedIn tends to be most relevant for specific locations
            if job.get("source") == "LinkedIn":
                score += 50
            return -score  # negative for ascending sort

        unique_jobs.sort(key=relevance_score)

    return unique_jobs
