"""
fetch_jobs.py — pulls remote PM/Partnerships/AI/Platform jobs from free sources.
No LLM calls. No API keys. Saves to jobs/YYYY-MM-DD_jobs.json.

Sources (all free, no auth):
- Remotive          — https://remotive.com/api/remote-jobs
- Arbeitnow         — https://www.arbeitnow.com/api/job-board-api
- Himalayas         — https://himalayas.app/jobs/api
- RemoteOK          — https://remoteok.com/api
- LinkedIn          — public guest endpoint, HTML parsed via BeautifulSoup
- Hiring.cafe       — internal POST API at hiring.cafe/api/search-jobs
- We Work Remotely  — RSS feeds per category
- Wellfound         — public search API (no auth required for basic queries)
- Remote.co         — RSS feed
- JobsPresso        — RSS feed

Queries are intentionally broad. Claude Code does the filtering at scoring time —
better to cast a wide net here than miss a good role with a non-standard title.
"""
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# Broad query list — covers PM variants, partnerships, BD, growth, AI, telecom, fintech
QUERIES = [
    "product manager",
    "senior product manager",
    "product owner",
    "principal product manager",
    "lead product manager",
    "digital product manager",
    "AI product manager",
    "GenAI product manager",
    "voice product manager",
    "platform product manager",
    "growth product manager",
    "fintech product manager",
    "telecom product manager",
    "partnerships manager",
    "platform partnerships",
    "business development manager",
    "commercial manager",
    "go to market manager",
    "head of product",
    "head of partnerships",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def norm(j: dict) -> dict:
    """Strip and trim a job record to a consistent shape."""
    return {
        "source": j.get("source", "unknown"),
        "title": (j.get("title") or "").strip(),
        "company": (j.get("company") or "").strip(),
        "location": (j.get("location") or "Remote").strip(),
        "url": (j.get("url") or "").strip(),
        "description": (j.get("description") or "")[:6000],
        "posted": j.get("posted", ""),
        "tags": j.get("tags", []),
    }


# ─── Source 1: Remotive ────────────────────────────────────────────────
def fetch_remotive(q: str) -> list:
    try:
        r = requests.get(
            f"https://remotive.com/api/remote-jobs?search={quote_plus(q)}",
            headers=HEADERS, timeout=30
        )
        r.raise_for_status()
        return [norm({
            "source": "remotive",
            "title": j.get("title"),
            "company": j.get("company_name"),
            "location": j.get("candidate_required_location"),
            "url": j.get("url"),
            "description": j.get("description", ""),
            "posted": j.get("publication_date", ""),
            "tags": j.get("tags", []),
        }) for j in r.json().get("jobs", [])]
    except Exception as e:
        print(f"  [remotive] '{q}' failed: {e}", file=sys.stderr)
        return []


# ─── Source 2: Arbeitnow ───────────────────────────────────────────────
def fetch_arbeitnow(q: str) -> list:
    try:
        r = requests.get(
            "https://www.arbeitnow.com/api/job-board-api",
            headers=HEADERS, timeout=30
        )
        r.raise_for_status()
        jobs = r.json().get("data", [])
        ql = q.lower()
        return [norm({
            "source": "arbeitnow",
            "title": j.get("title"),
            "company": j.get("company_name"),
            "location": j.get("location") or "Remote",
            "url": j.get("url"),
            "description": j.get("description", ""),
            "posted": j.get("created_at", ""),
            "tags": j.get("tags", []),
        }) for j in jobs
            if ql in (j.get("title", "") + " " + j.get("description", "")).lower()]
    except Exception as e:
        print(f"  [arbeitnow] '{q}' failed: {e}", file=sys.stderr)
        return []


# ─── Source 3: Himalayas ───────────────────────────────────────────────
def fetch_himalayas(q: str) -> list:
    try:
        r = requests.get(
            "https://himalayas.app/jobs/api",
            params={"search": q, "limit": 50},
            headers=HEADERS, timeout=30
        )
        if r.status_code != 200:
            return []
        return [norm({
            "source": "himalayas",
            "title": j.get("title"),
            "company": j.get("companyName"),
            "location": "Remote",
            "url": f"https://himalayas.app{j.get('applicationLink', '')}",
            "description": j.get("excerpt", ""),
            "posted": j.get("pubDate", ""),
        }) for j in r.json().get("jobs", [])]
    except Exception as e:
        print(f"  [himalayas] '{q}' failed: {e}", file=sys.stderr)
        return []


# ─── Source 4: RemoteOK ────────────────────────────────────────────────
def fetch_remoteok(q: str) -> list:
    try:
        r = requests.get(
            "https://remoteok.com/api",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        jobs = [j for j in data if isinstance(j, dict) and j.get("position")]
        ql = q.lower()
        return [norm({
            "source": "remoteok",
            "title": j.get("position"),
            "company": j.get("company"),
            "location": j.get("location") or "Remote",
            "url": j.get("url") or j.get("apply_url", ""),
            "description": j.get("description", ""),
            "posted": j.get("date", ""),
            "tags": j.get("tags", []),
        }) for j in jobs
            if ql in (j.get("position", "") + " " + " ".join(j.get("tags", []))).lower()]
    except Exception as e:
        print(f"  [remoteok] '{q}' failed: {e}", file=sys.stderr)
        return []


# ─── Source 5: LinkedIn (public guest endpoint) ───────────────────────
def fetch_linkedin(q: str, location: str = "Worldwide", max_pages: int = 2) -> list:
    """
    Uses LinkedIn's public 'guest' jobs endpoint — no auth required.
    Returns HTML cards which we parse with BeautifulSoup.
    Aggressively rate-limited by LinkedIn; expect 0 results sometimes.
    """
    results = []
    try:
        for page in range(max_pages):
            url = (
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={quote_plus(q)}"
                f"&location={quote_plus(location)}"
                f"&start={page * 25}"
                f"&f_TPR=r604800"  # posted in last week
            )
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                print(f"  [linkedin] rate-limited at page {page}, stopping", file=sys.stderr)
                break
            if r.status_code != 200:
                break

            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_="base-card") or soup.find_all("li")

            if not cards:
                break

            for card in cards:
                try:
                    title_el = card.find("h3", class_="base-search-card__title") \
                        or card.find("h3")
                    company_el = card.find("h4", class_="base-search-card__subtitle") \
                        or card.find("a", class_="hidden-nested-link")
                    loc_el = card.find("span", class_="job-search-card__location")
                    link_el = card.find("a", class_="base-card__full-link") \
                        or card.find("a", href=True)
                    time_el = card.find("time")

                    if not (title_el and link_el):
                        continue

                    job_url = link_el.get("href", "").split("?")[0]
                    results.append(norm({
                        "source": "linkedin",
                        "title": title_el.get_text(strip=True),
                        "company": company_el.get_text(strip=True) if company_el else "",
                        "location": loc_el.get_text(strip=True) if loc_el else location,
                        "url": job_url,
                        # LinkedIn doesn't expose full description in the search HTML
                        "description": f"LinkedIn listing. Title: {title_el.get_text(strip=True)}. "
                                       f"Open URL for full JD.",
                        "posted": time_el.get("datetime", "") if time_el else "",
                    }))
                except Exception:
                    continue

            time.sleep(1.5)  # be polite — LinkedIn is twitchy
    except Exception as e:
        print(f"  [linkedin] '{q}' failed: {e}", file=sys.stderr)
    return results


# ─── Source 6: Hiring.cafe ─────────────────────────────────────────────
def fetch_hiringcafe(q: str, size: int = 40) -> list:
    """
    Posts to hiring.cafe's internal /api/search-jobs endpoint.
    Schema is undocumented — based on community reverse-engineering.
    May need adjustment if their API shifts.
    """
    try:
        payload = {
            "size": size,
            "page": 0,
            "searchState": {
                "searchQuery": q,
                "locations": [
                    {"formatted_address": "Anywhere", "types": ["remote"]}
                ],
                "workplaceTypes": ["Remote"],
                "defaultToUserLocation": False,
                "user_id": None,
                "isRemote": True,
            }
        }
        r = requests.post(
            "https://hiring.cafe/api/search-jobs",
            json=payload,
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=30
        )
        if r.status_code != 200:
            print(f"  [hiringcafe] '{q}' returned {r.status_code}", file=sys.stderr)
            return []
        data = r.json()
        # Response shape varies; try the common keys
        items = data.get("results") or data.get("hits") or data.get("jobs") or []
        jobs = []
        for item in items:
            # Each item may wrap job in 'job_information' or be flat
            j = item.get("job_information", item)
            jobs.append(norm({
                "source": "hiringcafe",
                "title": j.get("title") or j.get("job_title") or item.get("title"),
                "company": (j.get("company") or j.get("company_name")
                            or item.get("company", {}).get("name", "")),
                "location": (j.get("location") or j.get("formatted_location")
                             or "Remote"),
                "url": (item.get("apply_url") or j.get("apply_url")
                        or item.get("job_url") or item.get("url", "")),
                "description": (j.get("description") or j.get("job_description")
                                or item.get("description", "")),
                "posted": item.get("created_at") or j.get("posted_at", ""),
            }))
        return [j for j in jobs if j["title"] and j["url"]]
    except Exception as e:
        print(f"  [hiringcafe] '{q}' failed: {e}", file=sys.stderr)
        return []


# ─── Source 7: We Work Remotely (RSS) ─────────────────────────────────
WWR_FEEDS = [
    # Each RSS feed covers a category; we pull the ones most relevant to PM/BD/Partnerships
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
    "https://weworkremotely.com/categories/remote-management-finance-jobs.rss",
    "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
    "https://weworkremotely.com/remote-jobs.rss",  # all jobs (broader net)
]

def fetch_weworkremotely(_q: str = "") -> list:
    """Fetches We Work Remotely RSS feeds — single call covers all categories."""
    seen_urls: set = set()
    results = []
    for feed_url in WWR_FEEDS:
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                def t(tag):
                    el = item.find(tag)
                    return el.text.strip() if el is not None and el.text else ""
                link = t("link")
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)
                # WWR encodes region in title like "Product Manager at Acme [Worldwide]"
                full_title = t("title")
                # region is in brackets at end
                company_el = item.find("{https://weworkremotely.com}company")
                company = company_el.text.strip() if company_el is not None and company_el.text else ""
                # strip region tag from title if present
                title = full_title.split(" at ")[0].strip() if " at " in full_title else full_title
                region_el = item.find("{https://weworkremotely.com}region")
                location = region_el.text.strip() if region_el is not None and region_el.text else "Remote"
                desc = t("description")
                # strip HTML from description
                try:
                    desc = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)
                except Exception:
                    pass
                results.append(norm({
                    "source": "weworkremotely",
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": link,
                    "description": desc[:6000],
                    "posted": t("pubDate"),
                }))
        except Exception as e:
            print(f"  [weworkremotely] {feed_url} failed: {e}", file=sys.stderr)
        time.sleep(0.5)
    return results


# ─── Source 8: Wellfound (formerly AngelList) ──────────────────────────
def fetch_wellfound(q: str) -> list:
    """
    Hits Wellfound's public talent search endpoint.
    No auth required for basic remote job listings.
    """
    try:
        r = requests.get(
            "https://wellfound.com/jobs",
            params={"q": q, "remote": "true"},
            headers={**HEADERS, "Accept": "text/html"},
            timeout=30,
        )
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        # Wellfound uses data-test attributes and React; try to find job cards
        cards = soup.find_all("div", attrs={"data-test": "StartupResult"}) or \
                soup.find_all("a", href=lambda h: h and "/jobs/" in h)
        for card in cards[:40]:
            try:
                title_el = card.find("span", attrs={"data-test": "FounderJobTitle"}) or \
                           card.find("h2") or card.find("h3")
                company_el = card.find("span", attrs={"data-test": "StartupName"}) or \
                             card.find("h4")
                link_el = card if card.name == "a" else card.find("a", href=True)
                if not (title_el and link_el):
                    continue
                href = link_el.get("href", "")
                url = f"https://wellfound.com{href}" if href.startswith("/") else href
                results.append(norm({
                    "source": "wellfound",
                    "title": title_el.get_text(strip=True),
                    "company": company_el.get_text(strip=True) if company_el else "",
                    "location": "Remote",
                    "url": url,
                    "description": f"Wellfound listing. Query: {q}. Open URL for full JD.",
                    "posted": "",
                }))
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"  [wellfound] '{q}' failed: {e}", file=sys.stderr)
        return []


# ─── Source 9: Remote.co (RSS) ────────────────────────────────────────
REMOTECO_FEEDS = [
    "https://remote.co/remote-jobs/product/feed/",
    "https://remote.co/remote-jobs/sales/feed/",
    "https://remote.co/remote-jobs/business-development/feed/",
    "https://remote.co/remote-jobs/manager/feed/",
]

def fetch_remoteco(_q: str = "") -> list:
    seen_urls: set = set()
    results = []
    for feed_url in REMOTECO_FEEDS:
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                def t(tag):
                    el = item.find(tag)
                    return el.text.strip() if el is not None and el.text else ""
                link = t("link")
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)
                desc = t("description")
                try:
                    desc = BeautifulSoup(desc, "html.parser").get_text(" ", strip=True)
                except Exception:
                    pass
                results.append(norm({
                    "source": "remoteco",
                    "title": t("title"),
                    "company": "",
                    "location": "Remote",
                    "url": link,
                    "description": desc[:6000],
                    "posted": t("pubDate"),
                }))
        except Exception as e:
            print(f"  [remoteco] {feed_url} failed: {e}", file=sys.stderr)
        time.sleep(0.3)
    return results


# ─── Main ──────────────────────────────────────────────────────────────
def main():
    all_jobs = []
    seen = set()
    per_source_count = {}

    # RSS-only sources run once (not per-query)
    rss_sources = [
        ("weworkremotely", fetch_weworkremotely),
        ("remoteco", fetch_remoteco),
    ]

    sources = [
        ("remotive", fetch_remotive),
        ("arbeitnow", fetch_arbeitnow),
        ("himalayas", fetch_himalayas),
        ("remoteok", fetch_remoteok),
        ("linkedin", fetch_linkedin),
        ("hiringcafe", fetch_hiringcafe),
        ("wellfound", fetch_wellfound),
    ]

    # Pull RSS feeds first (once, not per-query)
    print("\n=== Fetching RSS-based sources (single pass) ===")
    for name, fn in rss_sources:
        try:
            jobs = fn()
        except Exception as e:
            print(f"  [{name}] error: {e}", file=sys.stderr)
            jobs = []
        new = 0
        for j in jobs:
            if not j["url"] or j["url"] in seen:
                continue
            seen.add(j["url"])
            all_jobs.append(j)
            per_source_count[name] = per_source_count.get(name, 0) + 1
            new += 1
        print(f"  {name:16s} +{new:3d}  (running total: {len(all_jobs)})")

    print("\n=== Fetching query-based sources ===")
    for q in QUERIES:
        print(f"\nSearching: {q}")
        for name, fn in sources:
            try:
                jobs = fn(q)
            except TypeError:
                jobs = fn(q)
            new = 0
            for j in jobs:
                if not j["url"] or j["url"] in seen:
                    continue
                seen.add(j["url"])
                all_jobs.append(j)
                per_source_count[name] = per_source_count.get(name, 0) + 1
                new += 1
            print(f"  {name:16s} +{new:3d}  (running total: {len(all_jobs)})")
            time.sleep(0.5)

    all_source_names = [n for n, _ in rss_sources] + [n for n, _ in sources]
    print("\n" + "=" * 50)
    print("Source breakdown:")
    for name in all_source_names:
        print(f"  {name:16s} {per_source_count.get(name, 0):4d} jobs")
    print(f"  {'TOTAL':16s} {len(all_jobs):4d} unique jobs")
    print("=" * 50)

    Path("jobs").mkdir(exist_ok=True)
    out = Path(f"jobs/{date.today()}_jobs.json")
    out.write_text(json.dumps(all_jobs, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nSaved to {out}")
    print("Next: in Claude Code, say 'run workflow A'")


if __name__ == "__main__":
    main()
