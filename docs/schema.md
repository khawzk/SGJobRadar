# Data Schema

This project starts with JSON files instead of a database. The schema is intentionally close to a future Postgres model so migration stays simple.

## Raw Job

Stored under:

```text
data/raw/jobs_YYYY-MM-DD.json
```

Example:

```json
{
  "id": "adzuna-sg-123456",
  "source": "adzuna",
  "source_job_id": "123456",
  "country": "SG",
  "title": "Data Analyst",
  "company": "Example Company",
  "location": "Singapore",
  "category": "IT Jobs",
  "description": "We are looking for a Data Analyst with SQL and Python...",
  "salary_min": 5000,
  "salary_max": 7500,
  "currency": "SGD",
  "posted_at": "2026-05-20T00:00:00Z",
  "fetched_at": "2026-05-24T01:00:00Z",
  "url": "https://example.com/job/123456",
  "content_hash": "sha256..."
}
```

## Extracted Skill

```json
{
  "raw_job_id": "adzuna-sg-123456",
  "skill": "Python",
  "confidence": 1.0,
  "extraction_method": "keyword",
  "matched_text": "Python"
}
```

## Weekly Skill Stat

Stored under:

```text
data/weekly/skill_stats_YYYY-MM-DD.json
```

Example:

```json
{
  "week_start": "2026-05-18",
  "country": "SG",
  "skill": "Python",
  "job_count": 320,
  "previous_week_count": 260,
  "growth_rate": 0.2308
}
```

## Weekly Role Stat

```json
{
  "week_start": "2026-05-18",
  "country": "US",
  "role_family": "Data Analyst",
  "job_count": 860,
  "previous_week_count": 790,
  "growth_rate": 0.0886
}
```

## Latest Dashboard Payload

Stored at:

```text
data/latest.json
```

Shape:

```json
{
  "generated_at": "2026-05-24T01:30:00Z",
  "week_start": "2026-05-18",
  "markets": ["SG", "US"],
  "overview": {
    "total_jobs": 12000,
    "sg_jobs": 3000,
    "us_jobs": 9000
  },
  "top_skills": [],
  "growing_skills": [],
  "top_roles": [],
  "project_recommendations": []
}
```

