"""
High-level verification of critical sub-agent capabilities.

Each test pairs a natural-language style scenario with the tool invocation that
would satisfy it, ensuring planners have executable examples for screenshots,
presentations, zip/organize workflows, maps, email, attachments, and critiques.
"""

from pathlib import Path
import json
import zipfile
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from src.agent.file_agent import (
    create_zip_archive,
    take_screenshot,
    organize_files,
)
from src.agent.presentation_agent import (
    create_keynote,
    create_keynote_with_images,
    create_pages_doc,
)
from src.agent.email_agent import compose_email
from src.agent.maps_agent import plan_trip_with_stops
from src.agent.critic_agent import (
    verify_output,
    reflect_on_failure,
    validate_plan,
    check_quality,
)
from src.agent.screen_agent import capture_screenshot


def test_file_agent_create_zip_archive_creates_bundle(tmp_path):
    """Sample query: "Zip the rehearsal charts folder for sharing."""  # noqa: D401
    source_dir = tmp_path / "charts"
    source_dir.mkdir()
    (source_dir / "song1.txt").write_text("tab 1")
    (source_dir / "song2.txt").write_text("tab 2")

    result = create_zip_archive.invoke({
        "source_path": str(source_dir),
        "zip_name": "rehearsal_bundle.zip",
    })

    assert result["file_count"] == 2
    archive_path = Path(result["zip_path"])
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path) as zf:
        assert sorted(zf.namelist()) == ["song1.txt", "song2.txt"]


def test_file_agent_create_zip_archive_excludes_music(tmp_path):
    """Sample query: "Zip study materials, skip MP3 tracks."""  # noqa: D401
    study_dir = tmp_path / "study"
    study_dir.mkdir()
    (study_dir / "lecture.txt").write_text("Notes")
    (study_dir / "summary.pdf").write_text("Summary")
    (study_dir / "song.mp3").write_text("Audio")

    result = create_zip_archive.invoke({
        "source_path": str(study_dir),
        "zip_name": "study_stuff.zip",
        "exclude_extensions": ["mp3", "wav", "flac"],
    })

    assert not result.get("error"), f"ZIP creation failed: {result.get('error_message')}"
    archive_path = Path(result["zip_path"])
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path) as zf:
        names = sorted(zf.namelist())
        assert "song.mp3" not in names
        assert "lecture.txt" in names
        assert "summary.pdf" in names


def test_file_agent_default_source_directory(monkeypatch, tmp_path):
    """If source_path is omitted, the document directory should be used."""

    (tmp_path / "Alpha.pdf").write_text("alpha")
    (tmp_path / "Beta.txt").write_text("beta")

    monkeypatch.setattr(
        "src.agent.file_agent.load_config",
        lambda: {"document_directory": str(tmp_path)}
    )

    result = create_zip_archive.invoke({
        "zip_name": "alpha_archive.zip",
        "include_pattern": "A*"
    })

    assert not result.get("error")
    archive_path = Path(result["zip_path"])
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path) as zf:
        assert zf.namelist() == ["Alpha.pdf"]


def test_file_agent_take_screenshot_generates_png():
    """Sample query: "Capture page 1 from the AI Agents PDF."""  # noqa: D401
    pdf_path = PROJECT_ROOT / "test_docs" / "ai_agents_presentation.pdf"
    assert pdf_path.exists(), "test fixture missing"

    result = take_screenshot.invoke({
        "doc_path": str(pdf_path),
        "pages": [1],
    })

    assert result["pages_captured"] == [1]
    screenshot_path = Path(result["screenshot_paths"][0])
    assert screenshot_path.exists()
    assert screenshot_path.suffix == ".png"


def test_file_agent_organize_files_uses_llm_reasoning(monkeypatch, tmp_path):
    """Sample query: "Group every PDF into a deliverables folder."""  # noqa: D401
    # Patch heavy dependencies with light stubs
    import documents

    class DummyIndexer:
        def __init__(self, config):
            self.config = config

    class DummySearch:
        def __init__(self, indexer, config):
            self.indexer = indexer
            self.config = config

    monkeypatch.setattr(documents, "DocumentIndexer", DummyIndexer)
    monkeypatch.setattr(documents, "SemanticSearch", DummySearch)

    def fake_organize(self, category, target_folder, source_directory, search_engine=None, move=True):
        return {
            "success": True,
            "files_moved": ["score1.pdf", "score2.pdf"],
            "files_skipped": [],
            "target_path": str(tmp_path / target_folder),
            "reasoning": {
                "score1.pdf": f"Matches category {category}",
                "score2.pdf": f"Matches category {category}",
            },
            "total_evaluated": 2,
        }

    from automation import file_organizer as file_org_module
    monkeypatch.setattr(file_org_module.FileOrganizer, "organize_files", fake_organize)

    result = organize_files.invoke({
        "category": "deliverables",
        "target_folder": "organized_deliverables",
        "move_files": True,
    })

    assert result["files_moved"] == ["score1.pdf", "score2.pdf"]
    assert "organized_deliverables" in result["target_path"]
    assert "deliverables" in result["reasoning"]["score1.pdf"]


def _patch_keynote_composer(monkeypatch, tmp_path):
    """Utility to stub the macOS Keynote automation layer."""

    class DummyKeynoteComposer:
        def __init__(self, config):
            self.config = config

        def create_presentation(self, title, slides, output_path=None):
            path = Path(output_path) if output_path else (tmp_path / f"{title}.key")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{title} :: {len(slides)} slides")
            self.last_path = str(path)
            return True

    monkeypatch.setattr(
        "src.automation.keynote_composer.KeynoteComposer",
        DummyKeynoteComposer,
    )
    monkeypatch.setattr("src.automation.KeynoteComposer", DummyKeynoteComposer)


def test_presentation_agent_create_keynote_from_text(monkeypatch, tmp_path):
    """Sample query: "Create a Keynote deck covering Python basics."""  # noqa: D401
    _patch_keynote_composer(monkeypatch, tmp_path)

    out_path = tmp_path / "python_intro.key"
    result = create_keynote.invoke({
        "title": "Python Basics",
        "content": "History\n\nSyntax\n\nEcosystem",
        "output_path": str(out_path),
    })

    assert Path(result["keynote_path"]).exists()
    assert result["slide_count"] >= 2  # title slide + content


def test_presentation_agent_create_keynote_with_images(monkeypatch, tmp_path):
    """Sample query: "Turn these screenshots into a keynote."""  # noqa: D401
    _patch_keynote_composer(monkeypatch, tmp_path)

    image_path = tmp_path / "screenshot.png"
    image_path.write_bytes(b"fake-png")

    out_path = tmp_path / "screens.key"
    result = create_keynote_with_images.invoke({
        "title": "Automation Walkthrough",
        "image_paths": [str(image_path)],
        "content": "Slide 1\n• Step 1\n• Step 2",
        "output_path": str(out_path),
    })

    assert Path(result["keynote_path"]).exists()
    assert result["slide_count"] >= 2


def test_presentation_agent_create_pages_doc(monkeypatch, tmp_path):
    """Sample query: "Draft a Pages handout for the workshop."""  # noqa: D401

    class DummyPagesComposer:
        def __init__(self, config):
            self.config = config

        def create_document(self, title, sections, output_path=None):
            path = Path(output_path) if output_path else (tmp_path / f"{title}.pages")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(sections))
            return {"file_path": str(path)}

    monkeypatch.setattr(
        "src.automation.pages_composer.PagesComposer",
        DummyPagesComposer,
    )
    monkeypatch.setattr("src.automation.PagesComposer", DummyPagesComposer)

    out_path = tmp_path / "handout.pages"
    result = create_pages_doc.invoke({
        "title": "Workshop Handout",
        "content": "Overview\n\nAgenda\nSession 1\nSession 2",
        "output_path": str(out_path),
    })

    assert Path(result["pages_path"]).exists()


def test_email_agent_compose_email_with_attachment(monkeypatch, tmp_path):
    """Sample query: "Email the compiled report with attachment."""  # noqa: D401

    class DummyMailComposer:
        def __init__(self, config):
            self.config = config
            self.calls = []

        def compose_email(self, subject, body, recipient, attachment_paths=None, send_immediately=False):
            self.calls.append({
                "subject": subject,
                "body": body,
                "recipient": recipient,
                "attachments": attachment_paths or [],
                "send": send_immediately,
            })
            return True

    from automation import mail_composer as mail_module
    import src.automation.mail_composer as src_mail_module

    monkeypatch.setattr(mail_module, "MailComposer", DummyMailComposer)
    monkeypatch.setattr(src_mail_module, "MailComposer", DummyMailComposer)
    monkeypatch.setattr("automation.MailComposer", DummyMailComposer)
    monkeypatch.setattr("src.automation.MailComposer", DummyMailComposer)

    attachment = tmp_path / "report.pdf"
    attachment.write_text("dummy report")

    result = compose_email.invoke({
        "subject": "Automation Status",
        "body": "Attached is the latest report.",
        "recipient": "ops@example.com",
        "attachments": [str(attachment)],
        "send": True,
    })

    assert result["status"] == "sent"


def test_maps_agent_plan_trip_with_stops(monkeypatch):
    """Sample query: "Plan LA to SD with 1 fuel + 1 lunch stop."""  # noqa: D401

    def fake_stop_calculator(origin, destination, total, stop_types):
        return [
            {"location": "San Clemente, CA", "type": stop_types[0]},
            {"location": "Oceanside, CA", "type": stop_types[1]},
        ]

    monkeypatch.setattr(
        "src.agent.maps_agent._calculate_stop_points_with_llm",
        fake_stop_calculator,
    )

    result = plan_trip_with_stops.invoke({
        "origin": "Los Angeles, CA",
        "destination": "San Diego, CA",
        "num_fuel_stops": 1,
        "num_food_stops": 1,
        "departure_time": "7:00 AM",
        "use_google_maps": False,
        "open_maps": False,
    })

    assert result["total_stops"] == 2
    assert "maps://" in result["maps_url"]


def test_critic_agent_verify_output(monkeypatch):
    """Sample query: "Verify the summary satisfied the brief."""  # noqa: D401

    class DummyVerifier:
        def __init__(self, config):
            self.config = config

        def verify_step_output(self, **kwargs):
            return {
                "valid": True,
                "confidence": 0.92,
                "issues": [],
                "suggestions": [],
                "reasoning": "Matches intent",
            }

    monkeypatch.setattr("src.agent.verifier.OutputVerifier", DummyVerifier)

    result = verify_output.invoke({
        "step_description": "Summarize keynote feedback",
        "user_intent": "Provide 3 key takeaways",
        "actual_output": {"bullets": 3},
    })

    assert result["valid"] is True
    assert result["confidence"] == 0.92


def test_critic_agent_reflect_on_failure(monkeypatch):
    """Sample query: "Explain why the screenshot step failed."""  # noqa: D401

    class DummyReflection:
        def __init__(self, config):
            self.config = config

        def reflect_on_failure(self, **kwargs):
            return {
                "root_cause": "Window not focused",
                "corrective_actions": ["Refocus Stocks app", "Retry capture"],
                "retry_recommended": True,
                "alternative_approach": "Use web chart backup",
                "reasoning": "Screenshot target not visible",
            }

    monkeypatch.setattr("src.agent.verifier.ReflectionEngine", DummyReflection)

    result = reflect_on_failure.invoke({
        "step_description": "Capture Stocks chart",
        "error_message": "Window not found",
        "context": {"previous": []},
    })

    assert result["root_cause"] == "Window not focused"
    assert result["retry_recommended"] is True


def test_critic_agent_validate_plan(monkeypatch):
    """Sample query: "Validate the multi-step automation plan."""  # noqa: D401

    class DummyValidator:
        def __init__(self, tool_specs):
            self.tool_specs = tool_specs

        def validate_plan(self, plan):
            return True, []

    monkeypatch.setattr("src.orchestrator.validator.PlanValidator", DummyValidator)

    result = validate_plan.invoke({
        "plan": [{"id": 1, "action": "take_screenshot", "parameters": {}}],
        "goal": "Capture the PDF page",
        "available_tools": ["take_screenshot"],
    })

    assert result["valid"] is True
    assert result["errors"] == []


def test_critic_agent_check_quality(monkeypatch):
    """Sample query: "Score whether the report meets quality gates."""  # noqa: D401

    class DummyLLM:
        def __init__(self, *args, **kwargs):
            pass

        def invoke(self, messages):
            return type("Resp", (), {
                "content": json.dumps({
                    "passed": True,
                    "failed_criteria": [],
                    "score": 0.88,
                    "reasoning": "All criteria satisfied",
                })
            })()

    monkeypatch.setattr("src.agent.critic_agent.ChatOpenAI", DummyLLM)

    result = check_quality.invoke({
        "output": {"word_count": 500, "attachments": 1},
        "quality_criteria": {"min_word_count": 400, "attachments": True},
    })

    assert result["passed"] is True
    assert result["score"] == 0.88


def test_screen_agent_capture_screenshot(monkeypatch, tmp_path):
    """Sample query: "Grab a screenshot of the Stocks app window."""  # noqa: D401

    class DummyScreenCapture:
        def __init__(self, config):
            self.config = config

        def capture_screen(self, app_name=None, output_path=None):
            path = Path(output_path) if output_path else (tmp_path / "screen.png")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake")
            return {"screenshot_path": str(path)}

    monkeypatch.setattr(
        "src.automation.screen_capture.ScreenCapture",
        DummyScreenCapture,
    )

    result = capture_screenshot.invoke({
        "app_name": "Stocks",
        "output_name": "stocks_snap",
    })

    assert Path(result["screenshot_path"]).exists()
