import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = REPO_ROOT / "config" / "canonical_ids.yaml"
SLACK_EVENTS_PATH = REPO_ROOT / "data" / "synthetic_slack" / "slack_events.json"
GIT_EVENTS_PATH = REPO_ROOT / "data" / "synthetic_git" / "git_events.json"
GIT_PRS_PATH = REPO_ROOT / "data" / "synthetic_git" / "git_prs.json"


def _load_canonical_sets():
    data = yaml.safe_load(CANONICAL_PATH.read_text())
    return {
        "services": set(data["services"]),
        "components": set(data["components"]),
        "apis": set(data["apis"]),
        "docs": set(data["docs"]),
    }


def _load_json(path: Path):
    return json.loads(path.read_text())


def _assert_subset(values, allowed, context):
    unknown = sorted(set(values or []) - allowed)
    assert not unknown, f"{context} includes unknown IDs: {unknown}"


CANON = _load_canonical_sets()


def test_slack_events_use_canonical_ids():
    events = _load_json(SLACK_EVENTS_PATH)
    for event in events:
        ctx = f"slack event {event.get('id')}"
        _assert_subset(event.get("service_ids", []), CANON["services"], ctx)
        _assert_subset(event.get("component_ids", []), CANON["components"], ctx)
        _assert_subset(event.get("related_apis", []), CANON["apis"], ctx)


def test_git_events_use_canonical_ids():
    events = _load_json(GIT_EVENTS_PATH) + _load_json(GIT_PRS_PATH)
    for event in events:
        ctx = f"git event {event.get('id')}"
        _assert_subset(event.get("service_ids", []), CANON["services"], ctx)
        _assert_subset(event.get("component_ids", []), CANON["components"], ctx)
        _assert_subset(event.get("changed_apis", []), CANON["apis"], ctx)


def test_canonical_docs_exist():
    docs_root = REPO_ROOT / "data" / "synthetic_git"
    missing = []
    for rel_path in CANON["docs"]:
        matches = list(docs_root.glob(f"**/{rel_path}"))
        if not matches:
            missing.append(rel_path)
    assert not missing, f"Missing canonical doc files: {missing}"

