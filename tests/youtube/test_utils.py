from datetime import datetime

from src.youtube.models import VideoContext
from src.youtube.timestamp_parser import parse_timestamp_hint
from src.youtube.utils import (
    build_video_alias,
    extract_video_id,
    is_youtube_url,
    match_video_context,
)


def test_extract_video_id_handles_multiple_formats():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://example.com/video") is None


def test_is_youtube_url_detects_allowed_hosts():
    assert is_youtube_url("https://youtu.be/abc")
    assert is_youtube_url("https://youtube.com/watch?v=abc")
    assert not is_youtube_url("https://vimeo.com/123")


def test_build_video_alias_and_match_by_alias():
    ctx = VideoContext.from_metadata(
        "video123",
        "https://youtu.be/video123",
        build_video_alias("Transformer Insights", "video123"),
        metadata={"title": "Transformer Insights", "channel_title": "Cerebros"},
    )
    ctx.created_at = datetime.now().isoformat()
    matched, score = match_video_context("@{}".format(ctx.alias), [ctx])
    assert matched is ctx
    assert score == 1.0


def test_match_video_context_handles_titles():
    ctx = VideoContext.from_metadata(
        "abc",
        "https://youtu.be/abc",
        "transformers",
        metadata={"title": "Transformers 101", "channel_title": "AI Talks"},
    )
    matched, score = match_video_context("Transformers", [ctx])
    assert matched is ctx
    assert score > 0.5


def test_parse_timestamp_hint_variants():
    assert parse_timestamp_hint("what happens at 0:45?") == 45
    assert parse_timestamp_hint("around the 5-minute mark") == 300
    assert parse_timestamp_hint("jump to 1:02:03 please") == 3723
    assert parse_timestamp_hint("thirty seconds in") == 30

