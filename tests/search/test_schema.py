from datetime import datetime, timezone

from src.search.schema import UniversalEmbeddingPayload, build_context_chunk


def test_build_context_chunk_populates_metadata():
    payload = UniversalEmbeddingPayload(
        workspace_id="acme",
        source_type="slack",
        source_id="C123:1700000000.0001",
        parent_id="workspace:acme",
        display_name="incident update",
        path="slack/C123",
        start_offset=0.0,
        end_offset=10.0,
        url="https://slack.com/archives/C123/p17000000000001",
        modality_tags=["#incidents"],
        extra={"channel": "#incidents"},
        text="Service restored at 10:42 UTC",
        timestamp=datetime.now(timezone.utc),
    )

    chunk = build_context_chunk(payload)
    assert chunk.source_type == "slack"
    assert chunk.metadata["workspace_id"] == "acme"
    assert chunk.metadata["source_id"] == "C123:1700000000.0001"
    assert chunk.metadata["display_name"] == "incident update"
    assert "#incidents" in chunk.tags
    assert "slack" in chunk.tags
    assert any(tag.startswith("workspace:") for tag in chunk.tags)
    assert chunk.metadata["extra"]["channel"] == "#incidents"

