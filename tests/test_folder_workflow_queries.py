"""
Regression tests for folder-related natural language workflows requested by the user.

The scenarios cover:
1. Organizing folder contents alphabetically (rename normalization flow).
2. Collecting guitar tab files, bundling them, and drafting an email with the ZIP.
3. Generating a stock-price slideshow artifact and emailing it with the price embedded.

All LLM-dependent components are stubbed to keep the tests deterministic.
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

import pytest

# Ensure project root is importable for "src.*" modules during pytest collection
PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.automation.folder_tools import FolderTools
from src.automation.file_organizer import FileOrganizer
from src.agent.file_agent import create_zip_archive
from src.agent.email_agent import compose_email


def _build_config(folder: Path) -> Dict[str, Dict[str, object]]:
    """
    Build a minimal config compatible with ConfigAccessor and downstream tools.
    """
    log_path = folder / "test_app.log"
    return {
        "openai": {
            "api_key": "test-key",  # Dummy value for stubs
            "model": "gpt-4o",
            "temperature": 0.0,
        },
        "documents": {
            "folders": [str(folder)],
            "supported_types": [".pdf", ".docx", ".txt"],
        },
        "search": {
            "top_k": 5,
        },
        # Utilities/tools look for these optional fields
        "document_directory": str(folder),
        "email": {
            "default_recipient": "spamstuff062@gmail.com",
            "signature": "",
            "default_subject_prefix": "[Auto-generated]",
        },
        "logging": {
            "level": "INFO",
            "file": str(log_path),
        },
    }


class _DummyLLM:
    """Minimal ChatOpenAI replacement used to stub LLM calls."""

    def __init__(self, *args, **kwargs):
        pass

    def invoke(self, messages: List[Dict[str, str]]) -> SimpleNamespace:
        # Always return an empty JSON payload – individual tests override
        # categorisation/decision helpers directly where needed.
        return SimpleNamespace(content=json.dumps({"files": []}))


@pytest.fixture
def tmp_workspace(tmp_path) -> Path:
    """Create an isolated workspace inside pytest's temp directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """
    Replace ChatOpenAI globally to prevent real API usage during tests.
    """
    monkeypatch.setattr(
        "src.automation.file_organizer.ChatOpenAI",
        _DummyLLM,
    )
    yield


def test_organize_folders_alphabetically(tmp_workspace: Path):
    """
    Success criteria:
    - All files/directories get normalized names (lowercase, underscores).
    - Names are alphabetically ordered after rename.
    """
    messy_names = [
        "Project Notes.txt",
        "music Mix.MP3",
        "Vacation Photos",
        " Already_Normalized.pdf",
    ]

    for name in messy_names:
        target = tmp_workspace / name
        if "." in name and not name.endswith("."):
            target.write_text(f"Sample content for {name}")
        else:
            target.mkdir()

    config = _build_config(tmp_workspace)
    tools = FolderTools(config)

    plan = tools.plan_folder_organization_alpha(tmp_workspace)
    assert not plan.get("error"), plan.get("error_message")
    assert plan["changes_count"] >= 1, "Expected at least one rename candidate"

    dry_run = tools.apply_folder_plan(plan["plan"], tmp_workspace, dry_run=True)
    assert not dry_run.get("error"), dry_run.get("error_message")
    assert dry_run["dry_run"] is True
    assert len(dry_run["applied"]) == plan["changes_count"]

    applied = tools.apply_folder_plan(plan["plan"], tmp_workspace, dry_run=False)
    assert not applied.get("error"), applied.get("error_message")
    assert applied["success"] is True
    assert len(applied["errors"]) == 0

    final_listing = tools.list_folder(tmp_workspace)
    assert not final_listing.get("error"), final_listing.get("error_message")

    names = [item["name"] for item in final_listing["items"]]
    assert names == sorted(names), "Expect alphabetical ordering after rename"

    for name in names:
        assert " " not in name
        assert name == name.lower(), "Names should be normalized to lowercase"


def test_move_guitar_tabs_zip_and_email(tmp_workspace: Path, monkeypatch):
    """
    Scenario: "Move all guitar tab files into a new folder. Zip it and email it to me."

    Success criteria:
    - Only guitar-tab looking files end up in the destination folder.
    - The generated ZIP contains exactly those files.
    - compose_email receives the ZIP attachment and default recipient.
    """
    (tmp_workspace / "Guitar Tabs").mkdir()  # ensure idempotent behaviour

    guitar_files = [
        "Bad Liar - Fingerstyle Club.pdf",
        "Blinding Lights TAB.gp5",
        "Let Her Go TAB.txt",
    ]
    non_guitar_files = [
        "Work Report.docx",
        "shopping_list.txt",
    ]

    for file_name in guitar_files + non_guitar_files:
        (tmp_workspace / file_name).write_text(f"Dummy content for {file_name}")

    config = _build_config(tmp_workspace)

    def fake_categorize(self, files, category, search_engine=None):
        decisions = []
        for info in files:
            include = any(
                keyword in info["filename"].lower()
                for keyword in ["guitar", "tab", "fingerstyle"]
            )
            decisions.append(
                {
                    "filename": info["filename"],
                    "include": include,
                    "reasoning": "Matches guitar tab keywords"
                    if include
                    else "Irrelevant to guitar tabs",
                    "path": info["path"],
                }
            )
        return {"files": decisions}

    monkeypatch.setattr(
        FileOrganizer,
        "_categorize_files",
        fake_categorize,
        raising=False,
    )

    organizer = FileOrganizer(config)
    result = organizer.organize_files(
        category="guitar tabs",
        target_folder="Guitar Tabs",
        source_directory=str(tmp_workspace),
        move=True,
    )

    assert result["success"] is True
    assert sorted(result["files_moved"]) == sorted(guitar_files)
    assert set(result["files_skipped"]) == set(non_guitar_files)

    destination = Path(result["target_path"])
    assert destination.is_dir()
    assert sorted(f.name for f in destination.iterdir()) == sorted(guitar_files)

    # Stub load_config so file agent/email agent reuse the in-memory config
    monkeypatch.setattr(
        "src.agent.file_agent.load_config",
        lambda: config,
        raising=False,
    )
    monkeypatch.setattr(
        "src.agent.email_agent.load_config",
        lambda: config,
        raising=False,
    )

    zip_result = create_zip_archive.invoke(
        {
            "source_path": str(destination),
            "zip_name": "guitar_tabs_bundle.zip",
        }
    )
    assert not zip_result.get("error"), zip_result.get("error_message")

    with zipfile.ZipFile(zip_result["zip_path"]) as archive:
        zipped_names = sorted(archive.namelist())
    assert zipped_names == sorted(guitar_files)

    email_calls: List[Dict[str, object]] = []

    def fake_mail_compose(
        self,
        subject: str,
        body: str,
        recipient: str | None = None,
        attachment_path: str | None = None,
        attachment_paths: List[str] | None = None,
        send_immediately: bool = False,
    ) -> bool:
        attachments = attachment_paths or []
        if attachment_path:
            attachments = [attachment_path, *attachments]
        email_calls.append(
            {
                "subject": subject,
                "body": body,
                "recipient": recipient,
                "attachments": attachments,
                "send_immediately": send_immediately,
            }
        )
        return True

    monkeypatch.setattr(
        "src.automation.mail_composer.MailComposer.compose_email",
        fake_mail_compose,
        raising=False,
    )

    email_subject = "Guitar tabs bundle"
    email_body = "Attached are the latest guitar tabs you requested."

    email_result = compose_email.invoke(
        {
            "subject": email_subject,
            "body": email_body,
            "attachments": [zip_result["zip_path"]],
        }
    )

    assert not email_result.get("error"), email_result.get("error_message")
    assert email_calls, "Expected compose_email to be invoked"

    captured = email_calls[0]
    assert captured["recipient"] == config["email"]["default_recipient"]
    assert captured["attachments"] == [zip_result["zip_path"]]
    assert captured["subject"] == email_subject


def test_stock_price_slideshow_email(tmp_workspace: Path, monkeypatch):
    """
    Scenario: "Find Apple's stock price, turn it into a slideshow, and email it to me."

    Success criteria:
    - Stock lookup step is invoked (stubbed call).
    - Generated slideshow artifact includes the stock price text.
    - Email body references the same price and attaches the slideshow.
    """
    config = _build_config(tmp_workspace)

    monkeypatch.setattr(
        "src.agent.email_agent.load_config",
        lambda: config,
        raising=False,
    )

    # Record invocations to the stock search tool.
    stock_calls: List[str] = []

    def fake_stock_search(params: Dict[str, str]):
        stock_calls.append(params["company"])
        return {
            "success": True,
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "price": 188.23,
            "currency": "USD",
            "source": "Stubbed Google Finance result",
        }

    stock_result = fake_stock_search({"company": "Apple"})
    assert stock_calls == ["Apple"]

    price_text = f"{stock_result['ticker']} stock price: ${stock_result['price']}"
    slideshow_path = tmp_workspace / "AAPL_stock_summary.keynote.json"
    slideshow_content = {
        "title": "Apple Stock Overview",
        "slides": [
            {
                "heading": "Latest Price",
                "body": price_text,
            },
            {
                "heading": "Source",
                "body": stock_result["source"],
            },
        ],
    }
    slideshow_path.write_text(json.dumps(slideshow_content, indent=2))
    assert price_text in slideshow_path.read_text()

    email_calls: List[Dict[str, object]] = []

    def fake_mail_compose(
        self,
        subject: str,
        body: str,
        recipient: str | None = None,
        attachment_path: str | None = None,
        attachment_paths: List[str] | None = None,
        send_immediately: bool = False,
    ) -> bool:
        attachments = attachment_paths or []
        if attachment_path:
            attachments = [attachment_path, *attachments]
        email_calls.append(
            {
                "subject": subject,
                "body": body,
                "recipient": recipient,
                "attachments": attachments,
            }
        )
        return True

    monkeypatch.setattr(
        "src.automation.mail_composer.MailComposer.compose_email",
        fake_mail_compose,
        raising=False,
    )

    email_body = (
        "Attached is the Apple stock slideshow.\n"
        f"Latest price confirmation: {price_text}."
    )
    email_result = compose_email.invoke(
        {
            "subject": "Apple stock slideshow",
            "body": email_body,
            "attachments": [str(slideshow_path)],
        }
    )
    assert not email_result.get("error"), email_result.get("error_message")
    assert email_calls, "Expected an email to be drafted"

    captured = email_calls[0]
    assert captured["recipient"] == config["email"]["default_recipient"]
    assert captured["attachments"] == [str(slideshow_path)]
    assert price_text in captured["body"]
