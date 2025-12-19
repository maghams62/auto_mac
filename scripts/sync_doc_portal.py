#!/usr/bin/env python3
"""
Ensure every DocIssue record has a hosted page inside docs-portal and that each doc_url
points at the canonical GitHub Pages host.

Usage:
    python scripts/sync_doc_portal.py

Optional flags:
    --force-pages   Re-generate portal pages even if they already exist.
    --no-build      Skip the mkdocs build step after syncing pages.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

try:  # PyYAML may not be installed in every environment.
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - best effort
    yaml = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_PORTAL_DIR = REPO_ROOT / "docs-portal" / "docs"
CONFIG_PATH = REPO_ROOT / "config.yaml"
DEFAULT_DATASETS = [
    REPO_ROOT / "data" / "live" / "doc_issues.json",
    REPO_ROOT / "data" / "synthetic_git" / "doc_issues.json",
]
DEFAULT_PORTAL_BASE = "https://maghams62.github.io/docs-portal"
ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-(.*?))?\}")
SEARCH_ROOTS = [
    REPO_ROOT / "docs-portal",
    REPO_ROOT / "docs",
    REPO_ROOT / "frontend",
    REPO_ROOT / "src",
    REPO_ROOT / "oqoqo-dashboard",
    REPO_ROOT / "data",
]


def resolve_env_placeholders(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        var, default = match.group(1), match.group(2)
        return os.environ.get(var, default or "")

    return ENV_PATTERN.sub(repl, value)


def load_portal_config() -> tuple[str, Dict[str, str]]:
    """
    Return (portal_base_url, slug_map) from config.yaml if available, otherwise defaults.
    """

    if not CONFIG_PATH.exists() or yaml is None:
        return DEFAULT_PORTAL_BASE, {
            "docs/payments_api.md": "payments_api",
            "docs/billing_flows.md": "billing_flows",
        }

    data = yaml.safe_load(CONFIG_PATH.read_text())
    docs_cfg = data.get("docs") or {}
    base_raw = (docs_cfg.get("portal_base_url") or DEFAULT_PORTAL_BASE).strip()
    base_url = resolve_env_placeholders(base_raw)
    slug_map = docs_cfg.get("portal_slug_map") or {}
    return base_url or DEFAULT_PORTAL_BASE, slug_map


def normalize_doc_path(doc_path: str) -> str:
    """
    Mirror DocIssueService._normalize_doc_path behaviour so URLs match backend expectations.
    """

    value = (doc_path or "").strip().lstrip("/")
    if value.startswith("docs-portal/docs/"):
        value = value[len("docs-portal/docs/") :]
    elif value.startswith("docs/"):
        value = value[len("docs/") :]
    value = value.strip("/")
    if value.endswith(".md"):
        value = value[: -len(".md")]
    return value


def slug_to_rel_path(slug: str) -> Path:
    """
    Translate a slug (e.g., 'notification_playbook' or 'src/pages/Pricing.tsx')
    into a relative markdown path under docs-portal/docs/.
    """

    if not slug:
        raise ValueError("slug cannot be empty")
    rel = Path(*[segment for segment in slug.split("/") if segment])
    if rel.suffix:
        rel = rel.with_name(rel.name + ".md")
    else:
        rel = rel.with_suffix(".md")
    return rel


def find_source_file(doc_path: str) -> Optional[Path]:
    """
    Try to locate the original document so we can host the real content.
    """

    normalized = Path(doc_path.strip("/"))
    for prefix in ("", "docs-portal", "docs", "data"):
        candidate = (REPO_ROOT / prefix / normalized) if prefix else (REPO_ROOT / normalized)
        if candidate.is_file():
            return candidate

    filename = normalized.name
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        try:
            match = next(path for path in root.rglob(filename) if path.is_file())
            return match
        except StopIteration:
            continue
    return None


def build_page_content(
    *,
    doc_path: str,
    slug: str,
    issues: Sequence[Dict[str, object]],
    source_file: Optional[Path],
) -> str:
    """
    Compose markdown for a hosted page. Prefer the original markdown when available,
    otherwise fall back to auto-generated metadata.
    """

    primary = issues[0] if issues else {}
    title = str(primary.get("doc_title") or primary.get("summary") or slug or doc_path)
    title = title.strip() or doc_path

    if source_file and source_file.suffix.lower() == ".md":
        return source_file.read_text()

    lines: List[str] = [f"# {title}", ""]
    summaries = []
    for issue in issues:
        text = str(issue.get("summary") or "").strip()
        if text and text not in summaries:
            summaries.append(text)
    if summaries:
        lines.append("## Issue summary")
        for summary in summaries:
            lines.append(f"- {summary}")
        lines.append("")

    if source_file and source_file.exists():
        language = source_file.suffix.lstrip(".") or ""
        code = source_file.read_text()
        lines.append(f"```{language}")
        lines.append(code)
        lines.append("```")
        lines.append("")

    lines.append("## Doc issue metadata")
    for issue in issues:
        lines.append(
            f"- **{issue.get('id')}** "
            f"({issue.get('severity')}) – components: {', '.join(issue.get('component_ids') or [])}"
        )
    lines.append("")
    lines.append(f"_Source path: `{doc_path}`_")
    return "\n".join(lines)


def write_dataset(path: Path, payload: List[Dict[str, object]]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sync_doc_issues(
    *,
    dataset_paths: Iterable[Path],
    portal_base: str,
    slug_map: Dict[str, str],
) -> Dict[str, Dict[str, object]]:
    """
    Update doc_url values and aggregate doc issue metadata keyed by doc_path.
    """

    aggregates: Dict[str, Dict[str, object]] = {}
    for dataset_path in dataset_paths:
        if not dataset_path.exists():
            continue
        payload = json.loads(dataset_path.read_text())
        dirty = False
        for record in payload:
            doc_path = record.get("doc_path")
            if not doc_path:
                continue
            slug = slug_map.get(doc_path) or normalize_doc_path(doc_path)
            if not slug:
                continue
            target_url = f"{portal_base.rstrip('/')}/{slug.strip('/')}/"
            if record.get("doc_url") != target_url:
                record["doc_url"] = target_url
                dirty = True

            aggregates.setdefault(
                doc_path,
                {"slug": slug, "issues": []},
            )["issues"].append(record)

        if dirty:
            write_dataset(dataset_path, payload)

    return aggregates


def ensure_portal_pages(
    *,
    aggregates: Dict[str, Dict[str, object]],
    force: bool = False,
) -> List[Path]:

    generated: List[Path] = []
    for doc_path, info in aggregates.items():
        slug = info["slug"]
        target_rel = slug_to_rel_path(slug)
        target_path = DOCS_PORTAL_DIR / target_rel
        if target_path.exists() and not force:
            continue

        unique_issues = []
        seen_ids = set()
        for issue in info["issues"]:
            issue_id = issue.get("id")
            if issue_id and issue_id in seen_ids:
                continue
            if issue_id:
                seen_ids.add(issue_id)
            unique_issues.append(issue)

        source_file = find_source_file(doc_path)
        content = build_page_content(
            doc_path=doc_path,
            slug=slug,
            issues=unique_issues,
            source_file=source_file,
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content)
        generated.append(target_path)
    return generated


def run_mkdocs_build() -> None:
    subprocess.run(
        ["mkdocs", "build"],
        cwd=(REPO_ROOT / "docs-portal"),
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Host DocIssue references inside docs-portal.")
    parser.add_argument(
        "--force-pages",
        action="store_true",
        help="Rebuild portal pages even if they already exist.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip mkdocs build after syncing pages.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        help="Additional doc_issue dataset to process.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    portal_base, slug_map = load_portal_config()
    dataset_paths = list(DEFAULT_DATASETS)
    if args.datasets:
        dataset_paths.extend(Path(path) for path in args.datasets)

    aggregates = sync_doc_issues(
        dataset_paths=dataset_paths,
        portal_base=portal_base,
        slug_map=slug_map,
    )

    generated = ensure_portal_pages(
        aggregates=aggregates,
        force=args.force_pages,
    )

    if generated:
        rel_list = "\n  - ".join(str(path.relative_to(REPO_ROOT)) for path in generated)
        print(f"Generated portal pages:\n  - {rel_list}")
    else:
        print("No new portal pages were generated.")

    if not args.no_build:
        run_mkdocs_build()


if __name__ == "__main__":
    main()
