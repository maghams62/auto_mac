from __future__ import annotations

from scripts.seed_quota_demo import QuotaDemoSeeder
from src.config_manager import get_config


def build_seeder() -> QuotaDemoSeeder:
    config = get_config()
    return QuotaDemoSeeder(config, mode="synthetic", dry_run=True)


def test_slack_story_templates_cover_required_handles():
    seeder = build_seeder()
    templates = seeder._slack_story_templates()
    handles = {entry["handle"] for entry in templates}
    assert {"csm", "se", "billing", "docs", "pm"} <= handles
    formatted = templates[0]["text"].format(
        legacy=f"{seeder.quota.legacy:,}",
        updated=f"{seeder.quota.updated:,}",
    )
    normalized = formatted.replace(",", "")
    assert str(seeder.quota.legacy) in normalized
    assert str(seeder.quota.updated) in normalized


def test_doc_issue_summaries_include_quota_numbers():
    seeder = build_seeder()
    commits = seeder._build_synthetic_commits()
    issues = seeder._build_doc_issues(commits)
    legacy = f"{seeder.quota.legacy:,}"
    updated = f"{seeder.quota.updated:,}"
    matched = [
        issue
        for issue in issues
        if legacy in issue.get("summary", "") and updated in issue.get("summary", "")
    ]
    assert matched, "Expected at least one doc issue referencing both quota numbers."

