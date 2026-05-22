"""Collect job postings from Adzuna for SG and US."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from html import unescape
from pathlib import Path
from typing import Any

try:
    import certifi
except ImportError:  # pragma: no cover - optional local dependency
    certifi = None


ADZUNA_ENDPOINT = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
COUNTRY_TO_CURRENCY = {
    "sg": "SGD",
    "us": "USD",
}
TECH_QUERIES = [
    "software engineer",
    "frontend developer",
    "backend developer",
    "AI engineer",
    "machine learning engineer",
    "cloud engineer",
    "devops engineer",
    "data engineer",
    "cybersecurity",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect jobs from Adzuna.")
    parser.add_argument(
        "--countries",
        nargs="+",
        default=["sg"],
        choices=["sg", "us"],
        help="Countries to collect. Start with SG; add US when ready.",
    )
    parser.add_argument("--pages", type=int, default=1, help="Pages to fetch per country.")
    parser.add_argument(
        "--results-per-page",
        type=int,
        default=20,
        help="Adzuna results per page.",
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=TECH_QUERIES,
        help="Search queries to collect. Defaults to tech-focused roles.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="Directory for normalized raw job JSON files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and print planned requests without calling the API.",
    )
    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()


def stable_hash(parts: list[str]) -> str:
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def public_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_query = [(key, val) for key, val in query if key.lower() != "utm_source"]
    return urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        urllib.parse.urlencode(safe_query),
        parsed.fragment,
    ))


def fetch_page(
    country: str,
    page: int,
    query: str,
    app_id: str,
    app_key: str,
    results_per_page: int,
) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": results_per_page,
            "what": query,
            "category": "it-jobs",
            "content-type": "application/json",
        }
    )
    url = f"{ADZUNA_ENDPOINT.format(country=country, page=page)}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "market-skill-radar/0.1"})
    context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_job(
    country: str,
    query: str,
    query_total: int | None,
    job: dict[str, Any],
    fetched_at: str,
) -> dict[str, Any]:
    source_job_id = str(job.get("id", ""))
    title = clean_text(job.get("title"))
    company = clean_text((job.get("company") or {}).get("display_name"))
    location = clean_text((job.get("location") or {}).get("display_name"))
    category = clean_text((job.get("category") or {}).get("label"))
    description = clean_text(job.get("description"))
    url = public_url(job.get("redirect_url") or job.get("adref") or "")
    content_hash = stable_hash([title, company, location, description, url])

    return {
        "id": f"adzuna-{country}-{source_job_id}",
        "source": "adzuna",
        "source_query": query,
        "source_query_total": query_total,
        "source_job_id": source_job_id,
        "country": country.upper(),
        "title": title,
        "company": company,
        "location": location,
        "category": category,
        "description": description,
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "currency": COUNTRY_TO_CURRENCY[country],
        "posted_at": job.get("created"),
        "fetched_at": fetched_at,
        "url": url,
        "content_hash": content_hash,
    }


def dedupe_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for job in jobs:
        key = (job["source_job_id"], job["content_hash"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped


def write_country_jobs(output_dir: Path, country: str, jobs: list[dict[str, Any]]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    path = output_dir / f"adzuna_{country}_{today}.json"
    path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    if args.dry_run:
        for country in args.countries:
            for query in args.queries:
                for page in range(1, args.pages + 1):
                    print(f"Would fetch Adzuna country={country} query={query!r} page={page}")
        return

    app_id = require_env("ADZUNA_APP_ID")
    app_key = require_env("ADZUNA_APP_KEY")
    fetched_at = datetime.now(UTC).isoformat()

    for country in args.countries:
        normalized: list[dict[str, Any]] = []
        for query in args.queries:
            for page in range(1, args.pages + 1):
                payload = fetch_page(country, page, query, app_id, app_key, args.results_per_page)
                query_total = payload.get("count")
                normalized.extend(
                    normalize_job(country, query, query_total, job, fetched_at)
                    for job in payload.get("results", [])
                )

        deduped = dedupe_jobs(normalized)
        path = write_country_jobs(output_dir, country, deduped)
        print(f"Wrote {len(deduped)} {country.upper()} jobs to {path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
