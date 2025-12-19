from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .models import TranscriptChunk


def chunk_transcript_segments(
    video_id: str,
    segments: Iterable[Dict[str, float]],
    *,
    max_chars: int = 1200,
    overlap_seconds: float = 2.0,
) -> List[TranscriptChunk]:
    """
    Convert raw transcript segments into chunked transcript windows.
    """

    chunks: List[TranscriptChunk] = []
    buffer: List[str] = []
    chunk_start: Optional[float] = None
    chunk_end: Optional[float] = None
    index = 0

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue

        start = float(seg.get("start", 0.0))
        duration = float(seg.get("duration", 0.0))
        end = start + duration

        if chunk_start is None:
            chunk_start = start
            chunk_end = end

        projected_length = len("\n".join(buffer + [text]))
        if projected_length > max_chars and buffer:
            chunks.append(
                TranscriptChunk(
                    video_id=video_id,
                    index=index,
                    start_seconds=max(chunk_start - overlap_seconds, 0),
                    end_seconds=chunk_end or start,
                    text="\n".join(buffer),
                    token_count=_estimate_tokens(buffer),
                )
            )
            buffer = []
            chunk_start = start
            index += 1

        buffer.append(text)
        chunk_end = end

    if buffer and chunk_start is not None:
        chunks.append(
            TranscriptChunk(
                video_id=video_id,
                index=index,
                start_seconds=max(chunk_start - overlap_seconds, 0),
                end_seconds=chunk_end or chunk_start,
                text="\n".join(buffer),
                token_count=_estimate_tokens(buffer),
            )
        )

    return chunks


def _estimate_tokens(lines: List[str]) -> int:
    text = " ".join(lines)
    return max(1, len(text) // 4)

