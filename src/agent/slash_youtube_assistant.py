from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from ..services.youtube_context_service import YouTubeContextService
from ..youtube import (
    VideoContext,
    TranscriptChunk,
    TranscriptState,
    YouTubeHistoryStore,
    YouTubeMetadataClient,
    YouTubeTranscriptRetriever,
    YouTubeTranscriptService,
    YouTubeVectorIndexer,
    YouTubeTranscriptCache,
    extract_video_id,
    is_youtube_url,
    match_video_context,
    build_video_alias,
    parse_timestamp_hint,
    YouTubeGraphWriter,
    normalize_video_url,
)
from ..graph.service import GraphService
from ..graph.universal_nodes import UniversalNodeWriter
from ..youtube.ingestion_pipeline import YouTubeIngestionPipeline, YouTubeIngestionResult

logger = logging.getLogger(__name__)


@dataclass
class YouTubeQueryPlan:
    """Lightweight heuristics to guide retrieval + synthesis for /youtube questions."""

    question_type: str
    constraints: Dict[str, Any] = field(default_factory=dict)
    required_outputs: List[str] = field(default_factory=list)
    timestamp_seconds: Optional[int] = None
    timestamp_window: float = 25.0
    retrieval_top_k: int = 4
    focus_on_hosts: bool = False
    focus_on_concept: bool = True
    needs_key_moments: bool = False

    @classmethod
    def from_question(cls, question: str, timestamp_seconds: Optional[int]) -> "YouTubeQueryPlan":
        normalized = (question or "").strip().lower()
        required_outputs: List[str] = []
        question_type = "general"
        needs_key_moments = False
        focus_on_concept = any(keyword in normalized for keyword in ("concept", "explain", "overview", "what is"))

        if timestamp_seconds is not None:
            question_type = "timestamp_specific"
            required_outputs.append("describe_timestamp")
        elif any(token in normalized for token in ("chapter", "timeline", "moment", "timecode", "around", "at ")):
            question_type = "temporal"
            needs_key_moments = True

        host_keywords = ("host", "speaker", "presenter", "main guy", "main host", "who's hosting", "who is hosting")
        focus_on_hosts = any(keyword in normalized for keyword in host_keywords)
        if focus_on_hosts:
            required_outputs.append("identify_hosts")

        if any(token in normalized for token in ("topics", "list", "chapters", "key points", "highlights")):
            required_outputs.append("list_topics")
            needs_key_moments = True

        retrieval_top_k = 6 if needs_key_moments else 4
        timestamp_window = 35.0 if needs_key_moments else 20.0

        constraints: Dict[str, Any] = {}
        if timestamp_seconds is not None:
            constraints["timestamp_seconds"] = timestamp_seconds

        if not required_outputs:
            required_outputs.append("explain_concept" if focus_on_concept else "answer_question")

        return cls(
            question_type=question_type,
            constraints=constraints,
            required_outputs=required_outputs,
            timestamp_seconds=timestamp_seconds,
            timestamp_window=timestamp_window,
            retrieval_top_k=retrieval_top_k,
            focus_on_hosts=focus_on_hosts,
            focus_on_concept=focus_on_concept,
            needs_key_moments=needs_key_moments,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_type": self.question_type,
            "constraints": self.constraints,
            "required_outputs": self.required_outputs,
            "timestamp_seconds": self.timestamp_seconds,
            "timestamp_window": self.timestamp_window,
            "retrieval_top_k": self.retrieval_top_k,
            "focus_on_hosts": self.focus_on_hosts,
            "focus_on_concept": self.focus_on_concept,
            "needs_key_moments": self.needs_key_moments,
        }

class SlashYouTubeAssistant:
    """Deterministic interpreter for /youtube commands."""

    def __init__(
        self,
        agent_registry,
        session_manager,
        config: Optional[Dict[str, Any]] = None,
        *,
        context_service: Optional[YouTubeContextService] = None,
        history_store: Optional[YouTubeHistoryStore] = None,
        metadata_client: Optional[YouTubeMetadataClient] = None,
        transcript_service: Optional[YouTubeTranscriptService] = None,
        vector_indexer: Optional[YouTubeVectorIndexer] = None,
        retriever: Optional[YouTubeTranscriptRetriever] = None,
        transcript_cache: Optional[YouTubeTranscriptCache] = None,
    ):
        self.registry = agent_registry
        self.session_manager = session_manager
        self.config = config or {}
        youtube_cfg = self.config.get("youtube") or {}

        history_path = Path(youtube_cfg.get("history_path", "data/state/youtube_history.json"))
        clipboard_cfg = youtube_cfg.get("clipboard") or {}
        self.history_store = history_store or YouTubeHistoryStore(
            history_path,
            max_entries=int(youtube_cfg.get("max_recent", 8)),
            clipboard_enabled=bool(clipboard_cfg.get("enabled", True)),
        )
        self.context_service = context_service or YouTubeContextService(
            session_manager, self.history_store, self.config
        )
        self.metadata_client = metadata_client or YouTubeMetadataClient(self.config)
        self.transcript_service = transcript_service or YouTubeTranscriptService(self.config)
        self.vector_indexer = vector_indexer or YouTubeVectorIndexer(self.config)
        self.retriever = retriever or YouTubeTranscriptRetriever(
            self.config,
            vector_service=self.vector_indexer.vector_service,
        )
        cache_path = Path((youtube_cfg.get("transcript_cache") or {}).get("path", "data/state/youtube_videos"))
        self.transcript_cache = transcript_cache or YouTubeTranscriptCache(cache_path)

        vectordb_cfg = youtube_cfg.get("vectordb") or {}
        self.chunk_char_limit = int(vectordb_cfg.get("max_chunk_chars", 1200))
        self.chunk_overlap_seconds = float(vectordb_cfg.get("chunk_overlap_seconds", 2.0))
        self.clipboard_max = int(clipboard_cfg.get("max_candidates", 5))

        self.graph_service = GraphService(self.config)
        self.graph_writer = YouTubeGraphWriter(self.graph_service)
        self.universal_writer = UniversalNodeWriter(self.graph_service)
        self.ingestion_pipeline = YouTubeIngestionPipeline(
            metadata_client=self.metadata_client,
            transcript_service=self.transcript_service,
            vector_indexer=self.vector_indexer,
            transcript_cache=self.transcript_cache,
            graph_writer=self.graph_writer,
            universal_writer=self.universal_writer,
            chunk_char_limit=self.chunk_char_limit,
            chunk_overlap_seconds=self.chunk_overlap_seconds,
        )

        # Trace store is provided by SlashCommandHandler; set to None here and allow setter injection
        self.query_trace_store = None

        logger.info("[SLASH YOUTUBE] Assistant initialized (history=%s)", history_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def handle(self, task: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        # Pipeline overview:
        # 1. Parse `/youtube` selector and question.
        # 2. Attach/fetch metadata + transcript (with cache + vector indexing).
        # 3. Retrieve transcript chunks (timestamp-aware and semantic RAG).
        # 4. Synthesize a structured, direct answer for the user.
        task = (task or "").strip()
        if not task:
            return self._suggestion_payload(session_id)

        selector, remainder = self._parse_command(task)

        if selector and is_youtube_url(selector):
            return self._handle_url(selector, remainder, session_id)

        contexts = self.context_service.list_contexts(session_id)
        if not contexts:
            if is_youtube_url(task):
                return self._handle_url(task, None, session_id)
            return self._error("Paste a YouTube URL or attach a video first.")

        active = self.context_service.get_active_video(session_id)
        question = remainder
        target = None

        if selector:
            target, _score = match_video_context(selector, contexts)
            if not target and remainder and active:
                target = active
                question = task
            elif not target and not remainder:
                # User might be asking a question without alias; use entire task as question.
                question = task
                target = active
        else:
            target = active
            question = task

        if not target:
            return self._error("Could not match that video. Try referencing it by `@alias` or paste the URL.")

        self.context_service.set_active_video(session_id, target.video_id)
        self.context_service.touch_video(session_id, target.video_id)

        if not question:
            return self._format_attach_response(target, reused=True)

        return self._answer_question(target, question, session_id)

    # ------------------------------------------------------------------
    # Command handling helpers
    # ------------------------------------------------------------------
    def _handle_url(self, url: str, question: Optional[str], session_id: Optional[str]) -> Dict[str, Any]:
        video_id = extract_video_id(url)
        if not video_id:
            return self._error("I couldn't extract a YouTube video ID from that link.")

        alias = build_video_alias(None, video_id)
        metadata = self.metadata_client.fetch_metadata(video_id, url)
        alias = build_video_alias(metadata.get("title"), video_id, metadata.get("channel_title"))

        context = VideoContext.from_metadata(video_id, url, alias, metadata)
        context.transcript_status.mark_pending()
        self.context_service.save_context(session_id, context, make_active=True)

        ingestion = self._run_ingestion_pipeline(context, metadata, session_id)
        context = ingestion.video
        self.context_service.save_context(session_id, context, make_active=True)

        if ingestion.error:
            return self._error(
                ingestion.error,
                data={"video": context.summary_card()},
            )

        if question:
            return self._answer_question(context, question, session_id, reused=ingestion.reused)

        return self._format_attach_response(context, reused=ingestion.reused)

    def _run_ingestion_pipeline(
        self,
        context: VideoContext,
        metadata: Dict[str, Any],
        session_id: Optional[str],
    ) -> YouTubeIngestionResult:
        workspace_id = self.context_service.get_workspace_id()
        try:
            return self.ingestion_pipeline.ingest(
                context,
                metadata=metadata,
                session_id=session_id,
                workspace_id=workspace_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("[SLASH YOUTUBE] Ingestion pipeline failed for %s: %s", context.video_id, exc)
            context.transcript_status.mark_failed("ingest_error", str(exc))
            return YouTubeIngestionResult(
                video=context,
                metadata=metadata,
                error="I couldn't ingest that video. Try again later.",
            )

    def _answer_question(
        self,
        context: VideoContext,
        question: str,
        session_id: Optional[str],
        reused: bool = False,
    ) -> Dict[str, Any]:
        if not context.transcript_ready:
            status = context.transcript_status.state.value
            return self._error(
                f"Transcript is {status.replace('_', ' ')}. Try again soon.",
                data={"video": context.summary_card()},
            )

        timestamp_seconds = parse_timestamp_hint(question)
        plan = YouTubeQueryPlan.from_question(question, timestamp_seconds)

        if plan.timestamp_seconds is not None:
            segments = self.retriever.retrieve_by_timestamp(
                context,
                plan.timestamp_seconds,
                window=plan.timestamp_window,
            )
        else:
            segments = self.retriever.retrieve_semantic(
                context,
                question,
                top_k=plan.retrieval_top_k,
            )

        if not segments:
            return self._metadata_only_answer(context, plan)

        synthesis = self._synthesize_answer(context, question, segments, session_id, plan)
        if synthesis.get("error"):
            return synthesis

        structured = synthesis.get("structured_answer")
        structured_summary, structured_sections = self._render_structured_answer(context, plan, structured)

        summary_text = structured_summary or (
            synthesis.get("synthesized_content")
            or synthesis.get("summary")
            or synthesis.get("content")
            or synthesis.get("message")
            or "Answer synthesized from transcript segments."
        )
        if structured_sections:
            summary_text = "\n\n".join(part for part in [structured_summary, structured_sections] if part).strip()

        meta_line = synthesis.get("message") or synthesis.get("response")
        if meta_line == summary_text:
            meta_line = None

        references = self._format_segment_references(segments)
        sources = self._build_sources(context, segments)
        detail_parts = []
        if meta_line:
            detail_parts.append(meta_line)
        if references:
            detail_parts.append(references)
        details_text = "\n\n".join(detail_parts).strip()
        if reused:
            details_text = (details_text + ("\n\n(Using cached transcript)" if details_text else "(Using cached transcript)")).strip()

        evidence = [
            {
                "timestamp": self._format_timestamp(chunk.start_seconds),
                "start_seconds": chunk.start_seconds,
                "end_seconds": chunk.end_seconds,
                "text": chunk.text,
            }
            for chunk in segments
        ]

        trace_url = None
        if self.query_trace_store:
            trace_url = self._record_trace(question, context, segments)

        return {
            "type": "youtube_summary",
            "status": "success",
            "message": summary_text,
            "details": details_text,
            "sources": sources,
            "data": {
                "video": context.summary_card(),
                "retrieval": {
                    "timestamp_seconds": timestamp_seconds,
                    "plan": plan.to_dict(),
                },
                "segments": [
                    {
                        "start_seconds": chunk.start_seconds,
                        "end_seconds": chunk.end_seconds,
                        "text": chunk.text,
                    }
                    for chunk in segments
                ],
                "evidence": evidence,
                "trace_url": trace_url,
                "cached": reused,
                "sources": sources,
            },
        }

    def _synthesize_answer(
        self,
        context: VideoContext,
        question: str,
        segments: List[TranscriptChunk],
        session_id: Optional[str],
        plan: YouTubeQueryPlan,
    ) -> Dict[str, Any]:
        content_blocks = []
        for chunk in segments:
            timestamp = self._format_timestamp(chunk.start_seconds)
            content_blocks.append(f"[{timestamp}] {chunk.text}")

        plan_blob = json.dumps(plan.to_dict(), indent=2)
        metadata_blob = json.dumps(
            {
                "video_id": context.video_id,
                "title": context.title,
                "channel_title": context.channel_title,
                "description": (context.description or "")[:800],
                "duration_seconds": context.duration_seconds,
                "url": context.url,
                "tags": context.tags,
            },
            indent=2,
        )
        prompt = (
            "You are Cerebros' YouTube analyst. Follow the provided query plan and answer the user with a structured, multi-level explanation.\n"
            f"Query plan:\n{plan_blob}\n"
            f"Video metadata:\n{metadata_blob}\n"
            f"User question: {question}\n\n"
            "Instructions:\n"
            "1. Satisfy every required output from the plan (concepts, hosts, timestamps, etc.).\n"
            "2. Use only the transcript excerpts as evidence; cite approximate timestamps like 0:45.\n"
            "3. Connect the video to key concepts or other Cerebros sources whenever the transcript references them.\n"
            "4. Provide a channel-level note (audience, tone, recurring themes) using the metadata description/tags when explicit transcript evidence is missing.\n"
            "5. Mention limitations whenever evidence is missing.\n"
            "Return ONLY valid JSON with this shape (do not wrap in prose or code fences):\n"
            "{\n"
            '  \"gist\": \"One or two sentences that answer the user\",\n'
            '  \"sections\": [\n'
            '    {\"title\": \"High-level concept\", \"body\": \"Markdown paragraph(s)\", \"timestamp\": \"0:45\"},\n'
            '    {\"title\": \"Answer to your specific question\", \"body\": \"...\", \"timestamp\": \"1:20\"}\n'
            "  ],\n"
            '  \"key_concepts\": [\n'
            '    {\"name\": \"Concept\", \"summary\": \"Explanation\", \"timestamp\": \"2:10\", \"example\": \"Concrete example\"}\n'
            "  ],\n"
            '  \"hosts\": [\"Name or empty if unknown\"],\n'
            '  \"key_moments\": [{\"timestamp\": \"0:45\", \"summary\": \"What happens\"}],\n'
            '  \"channel_notes\": \"Describe channel focus/audience/style\",\n'
            '  \"related_context\": [\"Mention overlaps with Cerebros docs, Slack, Git, or well-known research if referenced\"],\n'
            '  \"extra_context\": [\"Optional caveats or metadata-based notes\"]\n'
            "}\n"
            "Always ensure the JSON is parseable and references only known information."
        )

        payload = {
            "source_contents": ["\n\n".join(content_blocks)],
            "topic": context.title or context.video_id,
            "synthesis_style": "comprehensive",
            "instructions": prompt,
            "user_question": question,
        }
        response = self.registry.execute_tool("synthesize_content", payload, session_id=session_id)
        raw_text = (
            response.get("synthesized_content")
            or response.get("summary")
            or response.get("content")
            or response.get("message")
            or ""
        )
        response["raw_text"] = raw_text
        response["structured_answer"] = self._parse_structured_answer(raw_text)
        return response

    def _record_trace(
        self,
        question: str,
        context: VideoContext,
        segments: List[TranscriptChunk],
    ) -> Optional[str]:
        if not self.query_trace_store:
            return None
        try:
            query_id = f"yt-{context.video_id}-{datetime.now(timezone.utc).timestamp():.0f}"
            from ..search.query_trace import QueryTrace, ChunkRef

            retrieved_refs = []
            for chunk in segments:
                retrieved_refs.append(
                    ChunkRef(
                        chunk_id=f"{context.video_id}:{chunk.index}",
                        source_type="youtube",
                        source_id=context.video_id,
                        modality="youtube",
                        title=context.title or context.video_id,
                        score=None,
                        url=context.url,
                        metadata={
                            "start_seconds": chunk.start_seconds,
                            "end_seconds": chunk.end_seconds,
                        },
                    )
                )

            trace = QueryTrace(
                query_id=query_id,
                question=question,
                modalities_used=["youtube"],
                retrieved_chunks=retrieved_refs,
                chosen_chunks=retrieved_refs,
            )
            self.query_trace_store.append(trace)
            return f"/brain/trace/{query_id}"
        except Exception as exc:
            logger.warning("[SLASH YOUTUBE] Failed to record query trace: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_attach_response(self, context: VideoContext, *, reused: bool) -> Dict[str, Any]:
        status = context.transcript_status.state.value
        message = (
            f"Linked **{context.title or context.video_id}**"
            if not reused
            else f"Using **{context.title or context.video_id}** ({context.alias})"
        )
        details = self._format_video_card(context, status)
        return {
            "type": "youtube_summary",
            "status": "success",
            "message": message,
            "details": details,
            "data": {"video": context.summary_card(), "cached": reused},
        }

    def _format_video_card(self, context: VideoContext, status: str) -> str:
        duration = self._format_timestamp(context.duration_seconds) if context.duration_seconds else "unknown"
        status_map = {
            "ready": "✅ Indexed",
            "pending": "⏳ Processing",
            "failed": "⚠️ Failed",
        }
        state_label = status_map.get(status, status)
        return "\n".join(
            [
                f"Channel: {context.channel_title or 'unknown'}",
                f"Duration: {duration}",
                f"Transcript: {state_label}",
                f"Alias: `@{context.alias}`",
            ]
        )

    def _format_segment_references(self, segments: List[TranscriptChunk]) -> str:
        lines = []
        for chunk in segments:
            ts = self._format_timestamp(chunk.start_seconds)
            preview = chunk.text.split("\n", 1)[0][:140]
            lines.append(f"- (~{ts}) {preview}")
        return "\n".join(lines)

    def _build_sources(self, context: VideoContext, segments: List[TranscriptChunk]) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(segments):
            start_label = self._format_timestamp(chunk.start_seconds)
            end_label = self._format_timestamp(chunk.end_seconds)
            snippet = chunk.text.split("\n", 1)[0][:200]
            url = normalize_video_url(
                context.video_id,
                playlist_id=context.playlist_id,
                timestamp=int(chunk.start_seconds),
            )
            sources.append(
                {
                    "title": context.title or context.video_id,
                    "subtitle": f"{start_label}–{end_label}",
                    "url": url,
                    "video_id": context.video_id,
                    "channel": context.channel_title,
                    "timestamp": start_label,
                    "start_seconds": chunk.start_seconds,
                    "end_seconds": chunk.end_seconds,
                    "snippet": snippet,
                    "rank": idx + 1,
                }
            )
        return sources

    def _parse_structured_answer(self, raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text:
            return None
        candidate = raw_text.strip()
        if candidate.startswith("```"):
            candidate = "\n".join(
                line
                for line in candidate.splitlines()
                if not line.strip().startswith("```")
            )
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        snippet = candidate[start : end + 1]
        try:
            data = json.loads(snippet)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            logger.debug("[SLASH YOUTUBE] Failed to parse structured answer JSON")
        return None

    def _render_structured_answer(
        self,
        context: VideoContext,
        plan: YouTubeQueryPlan,
        structured: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[str], Optional[str]]:
        if not structured:
            return None, None

        direct_answer = (
            structured.get("gist")
            or structured.get("direct_answer")
            or structured.get("summary")
            or ""
        ).strip() or None
        sections = structured.get("sections") or []
        section_blocks: List[str] = []
        for section in sections:
            title = (section.get("title") or "").strip()
            body = (section.get("body") or "").strip()
            if not title or not body:
                continue
            timestamp = (section.get("timestamp") or "").strip()
            ts_label = f" (~{timestamp})" if timestamp else ""
            heading = title if title.startswith("##") else f"## {title}{ts_label}"
            section_blocks.append(f"{heading}\n{body}")

        key_concepts = structured.get("key_concepts") or []
        if key_concepts:
            concept_lines = ["## Key concepts"]
            for concept in key_concepts:
                name = (concept.get("name") or "").strip()
                summary = (concept.get("summary") or "").strip()
                timestamp = (concept.get("timestamp") or "").strip()
                example = (concept.get("example") or "").strip()
                if not name and not summary:
                    continue
                bullet = f"- **{name or 'Concept'}**"
                if summary:
                    bullet += f": {summary}"
                if example:
                    bullet += f" (example: {example})"
                if timestamp:
                    bullet += f" ~{timestamp}"
                concept_lines.append(bullet)
            section_blocks.append("\n".join(concept_lines))

        hosts = structured.get("hosts") or []
        host_block = ""
        if hosts:
            host_block = "## Hosts & speakers\n" + "\n".join(f"- {host}" for host in hosts if host)
        elif plan.focus_on_hosts:
            fallback = context.channel_title or "this channel"
            host_block = (
                "## Hosts & speakers\n"
                f"I couldn’t confirm individual host names from the transcript, but the channel is {fallback}."
            )
        if host_block:
            section_blocks.append(host_block)

        key_moments = structured.get("key_moments") or []
        if key_moments:
            moment_lines = ["## Key moments"]
            for moment in key_moments:
                ts = moment.get("timestamp") or ""
                summary = (moment.get("summary") or "").strip()
                if summary:
                    prefix = f"({ts}) " if ts else ""
                    moment_lines.append(f"- {prefix}{summary}")
            section_blocks.append("\n".join(moment_lines))

        channel_notes = (
            (structured.get("channel_notes") or structured.get("channel_context") or "").strip()
        )
        if not channel_notes:
            channel_summary = (context.description or "").strip()
            if channel_summary:
                channel_notes = f"{context.channel_title or 'This channel'}: {channel_summary[:400]}"
        if channel_notes:
            section_blocks.append(f"## Channel overview\n{channel_notes}")

        related_context = structured.get("related_context") or []
        if related_context:
            rel_lines = ["## Related context"]
            for item in related_context:
                if item:
                    rel_lines.append(f"- {item}")
            section_blocks.append("\n".join(rel_lines))

        extra_context = structured.get("extra_context") or structured.get("notes") or []
        if extra_context:
            extras = ["## Extra context"]
            for note in extra_context:
                if note:
                    extras.append(f"- {note}")
            section_blocks.append("\n".join(extras))

        combined_sections = "\n\n".join(section_blocks).strip() or None
        return direct_answer, combined_sections

    def _metadata_only_answer(self, context: VideoContext, plan: YouTubeQueryPlan) -> Dict[str, Any]:
        title = context.title or context.video_id
        channel = context.channel_title or "Unknown channel"
        description = context.description or "No description available."
        limitations = "I couldn't retrieve transcript excerpts for that question, so this answer is based on metadata only."

        message_lines = [
            limitations,
            f"**Title:** {title}",
            f"**Channel:** {channel}",
            f"**Description:** {description.strip()}",
        ]
        if plan.focus_on_hosts and not context.channel_title:
            message_lines.append("Host names are not listed in the metadata.")

        return {
            "type": "youtube_summary",
            "status": "success",
            "message": "\n\n".join(message_lines),
            "details": "Try reattaching the video or asking about a different segment once transcripts are available.",
            "sources": [],
            "data": {
                "video": context.summary_card(),
                "segments": [],
                "retrieval": {"timestamp_seconds": plan.timestamp_seconds},
                "evidence": [],
                "cached": False,
                "sources": [],
            },
        }

    def _suggestion_payload(self, session_id: Optional[str]) -> Dict[str, Any]:
        suggestions = self.context_service.get_suggestions(
            session_id,
            limit=self.clipboard_max,
            include_clipboard=True,
        )
        return {
            "status": "success",
            "message": "Paste a YouTube URL or pick from recent videos.",
            "details": "",
            "data": suggestions,
        }

    def _error(self, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "status": "error",
            "message": message,
            "details": "",
            "data": data or {},
        }

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------
    def _parse_command(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        text = (text or "").strip()
        if not text:
            return None, None

        parts = text.split(maxsplit=1)
        selector = parts[0]
        remainder = parts[1] if len(parts) > 1 else None

        if is_youtube_url(selector):
            return selector, remainder
        return selector, remainder

    @staticmethod
    def _format_timestamp(seconds: Optional[float]) -> str:
        if seconds is None:
            return "0:00"
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

