"""Aggregate raw jobs into the dashboard payload."""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate raw jobs for the dashboard.")
    parser.add_argument("--raw-dir", default="data/raw", help="Directory containing raw job JSON.")
    parser.add_argument("--skills-file", default="skills.yml", help="Skill dictionary file.")
    parser.add_argument("--output", default="data/latest.json", help="Dashboard JSON output.")
    parser.add_argument("--weekly-dir", default="data/weekly", help="Directory for weekly snapshots.")
    return parser.parse_args()


def week_start(today: date) -> str:
    start = today - timedelta(days=today.weekday())
    return start.isoformat()


def load_raw_jobs(raw_dir: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.json")):
        if path.name.startswith("."):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            jobs.extend(payload)
    return jobs


def load_skills(path: Path) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- name:"):
            if current:
                skills.append(current)
            current = {"name": line.split(":", 1)[1].strip(), "aliases": []}
        elif current and line.startswith("aliases:"):
            alias_text = line.split(":", 1)[1].strip()
            if alias_text == "[]":
                current["aliases"] = []
            else:
                current["aliases"] = [
                    item.strip()
                    for item in alias_text.strip("[]").split(",")
                    if item.strip()
                ]
        elif current and line.startswith("category:"):
            current["category"] = line.split(":", 1)[1].strip()
        elif current and line.startswith("subcategory:"):
            current["subcategory"] = line.split(":", 1)[1].strip()

    if current:
        skills.append(current)

    return skills


def build_skill_patterns(skills: list[dict[str, Any]]) -> list[tuple[str, re.Pattern[str]]]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for skill in skills:
        terms = [skill["name"], *skill.get("aliases", [])]
        escaped = [re.escape(term) for term in terms if term]
        if not escaped:
            continue
        pattern = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(escaped) + r")(?![A-Za-z0-9])", re.I)
        patterns.append((skill["name"], pattern))
    return patterns


def skill_category_map(skills: list[dict[str, Any]]) -> dict[str, str]:
    return {
        skill["name"]: skill.get("category", "Other")
        for skill in skills
    }


def skill_subcategory_map(skills: list[dict[str, Any]]) -> dict[str, str]:
    return {
        skill["name"]: skill.get("subcategory", "General")
        for skill in skills
    }


def public_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value or "")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_query = [(key, val) for key, val in query if key.lower() != "utm_source"]
    return urllib.parse.urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        urllib.parse.urlencode(safe_query),
        parsed.fragment,
    ))


def infer_role_family(title: str) -> str:
    normalized = title.lower()
    role_patterns = [
        ("AI Engineer", ["ai engineer", "artificial intelligence", "generative ai", "llm"]),
        ("Cloud Engineer", ["cloud engineer", "cloud architect", "solution architect"]),
        ("DevOps Engineer", ["devops", "site reliability", "sre", "platform engineer"]),
        ("Cybersecurity", ["cybersecurity", "security engineer", "information security", "soc analyst"]),
        ("Frontend Developer", ["frontend", "front-end", "react developer", "ui developer"]),
        ("Backend Developer", ["backend", "back-end", "api developer"]),
        ("Software Engineer", ["software engineer", "software developer", "backend", "frontend", "full stack"]),
        ("Data Analyst", ["data analyst", "business intelligence", "bi analyst"]),
        ("Data Engineer", ["data engineer", "analytics engineer"]),
        ("Data Scientist", ["data scientist", "machine learning"]),
        ("Product Manager", ["product manager", "product owner"]),
        ("Project Manager", ["project manager", "programme manager", "program manager"]),
        ("Sales", ["sales", "account executive", "business development"]),
        ("Customer Success", ["customer success", "customer support", "customer service"]),
        ("Finance", ["finance", "accountant", "accounting", "auditor"]),
        ("Marketing", ["marketing", "growth", "brand"]),
        ("Operations", ["operations", "supply chain", "logistics"]),
        ("HR", ["human resources", "hr ", "recruiter", "talent acquisition"]),
        ("Designer", ["designer", "ux", "ui/ux", "creative"]),
        ("Engineer", ["engineer"]),
    ]

    for role, keywords in role_patterns:
        if any(keyword in normalized for keyword in keywords):
            return role
    return "Other"


def top_items(counter: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    return [{"name": name, "job_count": count} for name, count in counter.most_common(limit)]


def previous_week_path(weekly_dir: Path, current_week_start: str) -> Path | None:
    current = date.fromisoformat(current_week_start)
    previous = (current - timedelta(days=7)).isoformat()
    path = weekly_dir / f"latest_{previous}.json"
    return path if path.exists() else None


def growth_items(current: list[dict[str, Any]], previous: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous_counts = {item["name"]: item["job_count"] for item in previous}
    output = []
    for item in current:
        old = previous_counts.get(item["name"], 0)
        change = item["job_count"] - old
        growth_rate = None if old == 0 else change / old
        output.append({**item, "previous_count": old, "change": change, "growth_rate": growth_rate})
    return output


def grouped_skills(
    skill_counts: Counter[str],
    skill_categories: dict[str, str],
    skill_subcategories: dict[str, str],
    previous_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    group_totals: Counter[str] = Counter()
    group_skill_counts: dict[str, Counter[str]] = defaultdict(Counter)
    group_subcategory_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for skill, count in skill_counts.items():
        group = skill_categories.get(skill, "Other")
        subcategory = skill_subcategories.get(skill, "General")
        group_totals[group] += count
        group_skill_counts[group][skill] = count
        group_subcategory_counts[group][subcategory] += count

    previous_groups = {
        group["name"]: group.get("total_mentions", 0)
        for group in previous_payload.get("skill_groups", [])
    } if previous_payload else {}
    total_mentions = sum(group_totals.values()) or 1

    output = []
    for group, count in group_totals.most_common():
        previous_count = previous_groups.get(group, 0)
        output.append({
            "name": group,
            "total_mentions": count,
            "share": count / total_mentions,
            "previous_count": previous_count,
            "change": count - previous_count,
            "top_skills": top_items(group_skill_counts[group], 6),
            "subcategories": top_items(group_subcategory_counts[group], 8),
        })
    return output


def deep_dive_recommendations(skill_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations = []
    group_by_name = {group["name"]: group for group in skill_groups}
    ai_group = group_by_name.get("AI & Data")
    cloud_group = group_by_name.get("Cloud & DevOps")

    if ai_group:
        ai_subcategories = ai_group.get("subcategories", [])
        priority = ["Generative AI", "MLOps", "Retrieval Infrastructure", "Model API", "AI App Framework"]
        primary_ai = next(
            (item for name in priority for item in ai_subcategories if item["name"] == name),
            ai_subcategories[0] if ai_subcategories else {"name": "Generative AI", "job_count": 0},
        )
        strategic_ai_skills = [
            item["name"]
            for item in ai_group.get("top_skills", [])
            if item["name"] in {"LLM", "RAG", "MLOps", "OpenAI API", "Vector Database", "Embeddings", "LangChain", "Python"}
        ][:4]
        recommendations.append({
            "track": "AI direction",
            "focus": primary_ai["name"],
            "why": f"{primary_ai['name']} is the most strategic AI sub-signal to deepen, even if foundational Python/SQL mentions are higher.",
            "next_skills": strategic_ai_skills or [item["name"] for item in ai_group.get("top_skills", [])[:4]],
            "project": "Build a RAG-based job intelligence assistant with evaluation, source citations, and weekly skill trend memory.",
        })

    if cloud_group:
        cloud_subcategories = cloud_group.get("subcategories", [])
        primary_cloud = cloud_subcategories[0] if cloud_subcategories else {"name": "Cloud Platform", "job_count": 0}
        recommendations.append({
            "track": "Cloud/DevOps direction",
            "focus": primary_cloud["name"],
            "why": f"{primary_cloud['name']} is the strongest Cloud/DevOps sub-signal in this sample.",
            "next_skills": [item["name"] for item in cloud_group.get("top_skills", [])[:4]],
            "project": "Build a deployment observability dashboard that tracks CI/CD runs, cloud spend, uptime, and incident signals.",
        })

    return recommendations


def mini_trend_series(current: int, previous: int | None = None) -> list[dict[str, Any]]:
    if previous is None:
        previous = max(round(current * 0.82), 1)
    midpoint = round((previous + current) / 2)
    return [
        {"label": "Prev", "value": previous, "estimated": True},
        {"label": "Mid", "value": midpoint, "estimated": True},
        {"label": "Now", "value": current, "estimated": False},
    ]


def evidence_examples(
    jobs: list[dict[str, Any]],
    matched_skills_by_job: dict[str, list[str]],
    skill_categories: dict[str, str],
    limit: int = 6,
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    seen_groups: set[str] = set()

    ranked_jobs = sorted(
        jobs,
        key=lambda job: len(matched_skills_by_job.get(job.get("id", ""), [])),
        reverse=True,
    )

    for job in ranked_jobs:
        matched_skills = matched_skills_by_job.get(job.get("id", ""), [])
        if not matched_skills:
            continue

        groups = sorted({skill_categories.get(skill, "Other") for skill in matched_skills})
        if groups and groups[0] in seen_groups and len(examples) < 4:
            continue

        examples.append({
            "title": job.get("title", ""),
            "company": job.get("company") or "Unknown company",
            "location": job.get("location", ""),
            "source_query": job.get("source_query", ""),
            "matched_skills": matched_skills[:6],
            "skill_groups": groups,
            "url": public_url(job.get("url", "")),
        })
        seen_groups.update(groups)

        if len(examples) >= limit:
            break

    seen_ids = {
        f"{item['title']}|{item['company']}|{item['source_query']}"
        for item in examples
    }
    for job in ranked_jobs:
        if len(examples) >= limit:
            break

        matched_skills = matched_skills_by_job.get(job.get("id", ""), [])
        if not matched_skills:
            continue

        key = f"{job.get('title', '')}|{job.get('company') or 'Unknown company'}|{job.get('source_query', '')}"
        if key in seen_ids:
            continue

        groups = sorted({skill_categories.get(skill, "Other") for skill in matched_skills})
        examples.append({
            "title": job.get("title", ""),
            "company": job.get("company") or "Unknown company",
            "location": job.get("location", ""),
            "source_query": job.get("source_query", ""),
            "matched_skills": matched_skills[:6],
            "skill_groups": groups,
            "url": public_url(job.get("url", "")),
        })
        seen_ids.add(key)

    return examples


def aggregate(
    jobs: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    previous_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    country_counts = Counter(job.get("country", "Unknown") for job in jobs)
    category_counts = Counter(job.get("category") or "Unknown" for job in jobs)
    role_counts = Counter(infer_role_family(job.get("title", "")) for job in jobs)
    query_totals: dict[str, int] = {}
    for job in jobs:
        query = job.get("source_query") or "Unknown"
        total = job.get("source_query_total")
        if isinstance(total, int):
            query_totals[query] = max(query_totals.get(query, 0), total)
        else:
            query_totals[query] = query_totals.get(query, 0) + 1
    skill_counts: Counter[str] = Counter()
    skills_by_country: dict[str, Counter[str]] = defaultdict(Counter)
    matched_skills_by_job: dict[str, list[str]] = {}

    patterns = build_skill_patterns(skills)
    skill_categories = skill_category_map(skills)
    skill_subcategories = skill_subcategory_map(skills)
    for job in jobs:
        text = f"{job.get('title', '')} {job.get('description', '')}"
        matched = sorted({skill_name for skill_name, pattern in patterns if pattern.search(text)})
        matched_skills_by_job[job.get("id", "")] = matched
        for skill_name in matched:
            skill_counts[skill_name] += 1
            skills_by_country[job.get("country", "Unknown")][skill_name] += 1

    markets = sorted(country for country in country_counts if country != "Unknown")
    now = datetime.now(UTC).isoformat()

    top_skills = top_items(skill_counts, 12)
    top_roles = top_items(role_counts, 10)
    previous_skills = previous_payload.get("top_skills", []) if previous_payload else []
    previous_roles = previous_payload.get("top_roles", []) if previous_payload else []

    skill_groups = grouped_skills(skill_counts, skill_categories, skill_subcategories, previous_payload)
    total_market_matches = sum(query_totals.values())
    sampled_count = len(jobs)

    return {
        "generated_at": now,
        "week_start": week_start(date.today()),
        "markets": markets,
        "source_note": "Data source: Adzuna API. Focused on IT, software, AI, cloud, DevOps, data, and cybersecurity searches.",
        "comparison": {
            "has_previous_week": previous_payload is not None,
            "previous_week_start": previous_payload.get("week_start") if previous_payload else None,
        },
        "overview": {
            "sampled_jobs": sampled_count,
            "total_jobs": sampled_count,
            "market_matches": total_market_matches,
            "sg_jobs": country_counts.get("SG", 0),
            "us_jobs": country_counts.get("US", 0),
            "top_categories": top_items(category_counts, 8),
        },
        "demand_clusters": [
            {"name": name, "job_count": count}
            for name, count in sorted(query_totals.items(), key=lambda item: item[1], reverse=True)[:9]
        ],
        "top_skills": growth_items(top_skills, previous_skills),
        "skill_groups": skill_groups,
        "deep_dive_recommendations": deep_dive_recommendations(skill_groups),
        "trend_series": {
            "sampled_jobs": mini_trend_series(sampled_count),
            "market_matches": mini_trend_series(total_market_matches),
            "cloud_devops": mini_trend_series(next((group["total_mentions"] for group in skill_groups if group["name"] == "Cloud & DevOps"), 0)),
            "ai_data": mini_trend_series(next((group["total_mentions"] for group in skill_groups if group["name"] == "AI & Data"), 0)),
        },
        "growing_skills": growth_items(top_skills, previous_skills),
        "top_roles": growth_items(top_roles, previous_roles),
        "skills_by_country": {
            country: top_items(counter, 10)
            for country, counter in sorted(skills_by_country.items())
        },
        "evidence_examples": evidence_examples(
            jobs,
            matched_skills_by_job,
            skill_categories,
        ),
        "methodology": {
            "source": "Adzuna API",
            "market": "Singapore",
            "sampled_jobs": len(jobs),
            "market_matches": total_market_matches,
            "queries": sorted(query_totals.keys()),
            "skill_extraction": "Keyword dictionary from skills.yml, grouped into skillset categories.",
            "limits": [
                "Jobs analyzed means the postings actually read on the snapshot date for skill extraction.",
                "Demand index means the wider market signal from the tracked search topics; use it for relative demand, not exact job count.",
                "Skill counts depend on what employers explicitly write in job descriptions.",
                "Real trend lines start after the next scheduled snapshot.",
            ],
        },
        "project_recommendations": [
            {
                "name": "Cloud Skill Tracker for SG Tech Jobs",
                "why": "Azure, AWS, Kubernetes and Docker are visible in the current focused SG tech snapshot.",
                "suggested_stack": ["Python", "React", "Cloud APIs"],
            },
            {
                "name": "AI Job Requirements Explorer",
                "why": "LLM and RAG already appear in the first SG tech sample, but need tracking across more weeks.",
                "suggested_stack": ["Python", "LLM", "RAG"],
            }
        ],
        "takeaways": [
            "This dashboard is currently SG-only and tech-focused.",
            "This snapshot has no earlier baseline yet; the next scheduled snapshot will unlock trend deltas.",
            "React, Azure, AWS, Python and TypeScript are the strongest early skill signals in this sample.",
            "Skillsets are grouped into Frontend, Backend, Cloud & DevOps, AI & Data, Security, and BI & Analytics.",
        ],
    }


def main() -> None:
    args = parse_args()
    jobs = load_raw_jobs(Path(args.raw_dir))
    skills = load_skills(Path(args.skills_file))
    current_week = week_start(date.today())
    weekly_dir = Path(args.weekly_dir)
    previous_path = previous_week_path(weekly_dir, current_week)
    previous_payload = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path else None
    payload = aggregate(jobs, skills, previous_payload)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_path = weekly_dir / f"latest_{current_week}.json"
    weekly_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote dashboard payload for {len(jobs)} jobs to {output}")


if __name__ == "__main__":
    main()
