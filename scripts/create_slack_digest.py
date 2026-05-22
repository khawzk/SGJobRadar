"""Create a Slack-ready digest from data/latest.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Slack digest text.")
    parser.add_argument("--input", default="data/latest.json", help="Dashboard payload.")
    parser.add_argument("--dashboard-url", default="http://localhost:8000/dashboard/")
    return parser.parse_args()


def find_item(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((item for item in items if item.get("name") == name), {})


def find_track(items: list[dict[str, Any]], track: str) -> dict[str, Any]:
    return next((item for item in items if item.get("track") == track), {})


def create_digest(payload: dict[str, Any], dashboard_url: str) -> str:
    snapshot_date = payload.get("generated_at", "")[:10] or payload.get("week_start", "pending")
    overview = payload.get("overview", {})
    top_topic = (payload.get("demand_clusters") or [{}])[0].get("name", "pending")
    top_group = (payload.get("skill_groups") or [{}])[0].get("name", "pending")
    ai_direction = find_track(payload.get("deep_dive_recommendations", []), "AI direction")
    next_skills = ", ".join(f"`{skill}`" for skill in ai_direction.get("next_skills", [])) or "`pending`"

    return "\n".join([
        f"**SG Tech Market Radar — Snapshot {snapshot_date}**",
        "",
        f"- Jobs analyzed: `{overview.get('sampled_jobs', overview.get('total_jobs', 0))}`",
        f"- Hottest tracked topic: `{top_topic.title()}`",
        f"- Top skillset: `{top_group}`",
        f"- AI direction to dive deeper: `{ai_direction.get('focus', 'pending')}`",
        f"- Suggested next skills: {next_skills}",
        "",
        "Recommended build:",
        f"`{ai_direction.get('project', 'Review dashboard recommendations.')}`",
        "",
        "Dashboard:",
        dashboard_url,
    ])


def main() -> None:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(create_digest(payload, args.dashboard_url))


if __name__ == "__main__":
    main()

