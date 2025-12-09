import json
import logging
import os
import re
import difflib
from collections import Counter
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..reasoners import DocDriftAnswer, DocDriftReasoner
from ..services.git_metadata import GitMetadataService
from ..services.slash_query_plan import SlashQueryIntent, SlashQueryPlan
from ..slash_git.formatter import SlashGitLLMFormatter
from ..slash_git.models import GitQueryPlan
from ..slash_git.pipeline import SlashGitPipeline, SlashGitPipelineResult
from src.agent.evidence import git_commit_evidence_id, git_pr_evidence_id
from src.settings.automation import allows_auto_suggestions
from src.settings.git import resolve_repo_branch

logger = logging.getLogger(__name__)


class SlashGitAssistant:
    """
    Deterministic interpreter for /git commands.

    Responsibilities:
    - Track logical branch context per session
    - Map natural-language git questions to Git agent tools
    - Format graph-aware summaries highlighting entities + relationships
    """

    CONTEXT_KEY = "slash_git_active_branch"

    DOC_DRIFT_KEYWORDS = {
        "drift",
        "doc",
        "docs",
        "documentation",
        "payment",
        "payments",
        "vat",
        "notification",
        "notifications",
        "template",
        "template_version",
        "receipt",
    }
    GRAPH_ONLY_BLOCKED_TOOLS = {
        "list_recent_prs",
        "get_pr_details",
        "get_repo_overview",
        "list_repository_branches",
        "list_branch_commits",
        "search_branch_commits",
        "get_commit_details",
        "list_file_history",
        "compare_git_refs",
        "list_repository_tags",
        "get_latest_repo_tag",
        "list_branch_pull_requests",
    }

    def __init__(
        self,
        agent_registry,
        session_manager=None,
        config: Optional[Dict[str, Any]] = None,
        reasoner: Optional[DocDriftReasoner] = None,
        *,
        git_pipeline: Optional[SlashGitPipeline] = None,
        git_formatter: Optional[SlashGitLLMFormatter] = None,
        metadata_service: Optional[GitMetadataService] = None,
    ):
        self.registry = agent_registry
        self.session_manager = session_manager
        self.config = config or {}
        self._default_branch_cache: Optional[str] = None
        self._git_agent = None
        slash_git_cfg = self.config.get("slash_git") or {}
        self.debug_block_enabled = slash_git_cfg.get("debug_block_enabled", True)
        self.debug_source_label = slash_git_cfg.get("debug_source_label") or "synthetic_git"
        reasoner_enabled = slash_git_cfg.get("doc_drift_reasoner", True)
        env_token = os.getenv("GITHUB_TOKEN")
        github_cfg = (self.config.get("github") or {})
        self.debug_repo_label = slash_git_cfg.get("debug_repo_label") or github_cfg.get("repo_name") or "repository"
        self.github_token_configured = bool(env_token or github_cfg.get("token"))
        if not self.github_token_configured:
            logger.warning("[SLASH GIT] GITHUB_TOKEN missing; API calls will use anonymous rate limits.")
        self._last_tool_source: Optional[str] = None
        self._active_query_plan: Optional[Dict[str, Any]] = None
        self._plan_obj: Optional["SlashQueryPlan"] = None
        self.metadata_service = metadata_service or GitMetadataService(self.config)
        owner = github_cfg.get("repo_owner")
        repo_name = github_cfg.get("repo_name")
        self._repo_identifier = f"{owner}/{repo_name}" if owner and repo_name else None

        impact_cfg = self.config.get("impact") or {}
        self.impact_auto_enabled = allows_auto_suggestions("api_params")
        self.impact_endpoint_base = impact_cfg.get("endpoint_base") or os.getenv("IMPACT_ENDPOINT_BASE")
        graph_cfg = slash_git_cfg.get("graph_mode") or {}
        self.graph_only_mode = bool(graph_cfg.get("require", False))

        if reasoner_enabled:
            if reasoner is not None:
                self.doc_drift_reasoner = reasoner
            else:
                try:
                    self.doc_drift_reasoner = DocDriftReasoner(self.config)
                except Exception as exc:
                    logger.warning("[SLASH GIT] Doc drift reasoner unavailable: %s", exc)
                    self.doc_drift_reasoner = None
        else:
            self.doc_drift_reasoner = None

        if git_pipeline is not None:
            self.git_pipeline = git_pipeline
        else:
            try:
                self.git_pipeline = SlashGitPipeline(self.config, metadata_service=self.metadata_service)
            except Exception as exc:
                logger.warning("[SLASH GIT] Pipeline unavailable: %s", exc)
                self.git_pipeline = None

        if git_formatter is not None:
            self.git_formatter = git_formatter
        else:
            try:
                self.git_formatter = SlashGitLLMFormatter(self.config)
            except Exception as exc:
                logger.warning("[SLASH GIT] Formatter unavailable: %s", exc)
                self.git_formatter = None

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    def handle(
        self,
        task: str,
        session_id: Optional[str] = None,
        plan: Optional["SlashQueryPlan"] = None,
    ) -> Dict[str, Any]:
        """Main entrypoint invoked by the slash command handler."""
        task = (task or "").strip()
        if not task:
            return self._error_response("Please provide a Git question.")

        plan_dict = plan.to_dict() if plan else None
        self._active_query_plan = plan_dict
        self._plan_obj = plan
        try:
            if plan:
                task = self._apply_plan_to_task(task, plan)
            lower = task.lower()

            reasoned = self._maybe_handle_doc_drift(task)
            if reasoned is not None:
                if plan_dict:
                    metadata = reasoned.setdefault("metadata", {})
                    metadata["query_plan"] = plan_dict
                return reasoned

            pipeline_response = self._maybe_run_git_pipeline(task, lower, plan=self._plan_obj)
            if pipeline_response:
                return pipeline_response

            if self._looks_like_branch_switch(task):
                return self._handle_branch_switch(task, session_id)

            if self._looks_like_branch_query(lower):
                return self._handle_show_branch(session_id)

            if "repo" in lower and any(kw in lower for kw in ["info", "about", "what"]):
                return self._handle_repo_info(session_id)

            if "branches" in lower and ("list" in lower or "show" in lower or lower.strip() == "branches"):
                return self._handle_list_branches(session_id)

            if "pr" in lower or "pull request" in lower:
                return self._handle_branch_prs(task, session_id)

            if "tag" in lower:
                if "latest" in lower or "recent" in lower or "current" in lower:
                    return self._handle_latest_tag(session_id)
                return self._handle_list_tags(session_id)

            ref_pair = self._extract_ref_pair(task)
            if ref_pair:
                return self._handle_compare_refs(ref_pair[0], ref_pair[1], session_id)

            sha = self._extract_sha(task)
            if sha and ("commit" in lower or lower.startswith(sha)):
                include_files = any(kw in lower for kw in ["file", "summary", "changed", "diff", "what changed"])
                return self._handle_commit_details(sha, include_files=include_files, session_id=session_id)

            if ("files changed" in lower or "files touched" in lower) and "last commit" in lower:
                return self._handle_last_commit_files(session_id)
            if ("files changed" in lower or "files touched" in lower) and sha:
                return self._handle_commit_files(sha, session_id)

            file_path = self._extract_file_path(task)
            if file_path and any(kw in lower for kw in ["history", "last changed", "last change", "changes to"]):
                return self._handle_file_history(file_path, session_id)

            if "search commits" in lower or "commits mentioning" in lower:
                keyword = self._extract_search_keyword(task)
                return self._handle_commit_search(keyword, session_id)

            author = self._extract_author(task)
            if author:
                return self._handle_recent_commits(session_id, author=author)

            since_iso = self._extract_since_timestamp(task)
            if since_iso:
                return self._handle_recent_commits(session_id, since=since_iso)

            limit = self._extract_limit(task)
            if limit:
                return self._handle_recent_commits(session_id, limit=limit)

            if any(kw in lower for kw in ["last commit", "latest commit", "head commit"]):
                return self._handle_last_commit(session_id)

            if "commits" in lower:
                return self._handle_recent_commits(session_id)

            # Fallback to repo info if intent is unclear
            return self._handle_repo_info(session_id)
        finally:
            self._active_query_plan = None
            self._plan_obj = None

    def _apply_plan_to_task(self, task: str, plan: "SlashQueryPlan") -> str:
        if not plan or not plan.targets:
            return task
        extras: List[str] = []
        for target in plan.targets:
            if target.target_type not in {"repository", "component"}:
                continue
            token = target.identifier or target.label or target.raw
            if token:
                extras.append(str(token))
        if not extras:
            return task
        suffix = " ".join(extras)
        base_text = task or ""
        if suffix.lower() in base_text.lower():
            return base_text
        return f"{base_text} {suffix}".strip()

    def _maybe_handle_doc_drift(self, task: str) -> Optional[Dict[str, Any]]:
        if not self.doc_drift_reasoner:
            return None
        if not self._should_use_doc_drift_reasoner(task):
            return None
        try:
            answer = self.doc_drift_reasoner.answer_question(task, source="git")
        except Exception as exc:
            logger.warning("[SLASH GIT] Doc drift reasoner failed: %s", exc)
            return None
        return self._format_reasoner_response(answer)

    def _should_use_doc_drift_reasoner(self, task: str) -> bool:
        lower = (task or "").lower()
        if not lower:
            return False
        return any(keyword in lower for keyword in self.DOC_DRIFT_KEYWORDS)

    def _format_reasoner_response(self, answer: DocDriftAnswer) -> Dict[str, Any]:
        summary = answer.summary or "Doc drift summary unavailable."
        sections = answer.sections or {}
        lines: List[str] = []
        for topic in sections.get("topics") or []:
            title = topic.get("title") or "Topic"
            insight = topic.get("insight") or ""
            lines.append(f"- {title}: {insight}")
        if answer.next_steps:
            lines.append("Next steps:")
            lines.extend(f"  • {step}" for step in answer.next_steps)
        details = "\n".join(lines)
        data = {
            "scenario": answer.scenario.name,
            "api": answer.scenario.api,
            "impacted": answer.impacted,
            "doc_drift": answer.doc_drift,
            "evidence": answer.evidence,
        }
        status = "success" if not answer.error else "completed"
        if answer.error:
            data["reasoner_error"] = answer.error
        return {
            "type": "slash_git_summary",
            "status": status,
            "message": summary,
            "details": details,
            "data": data,
            "sources": answer.sources,
        }

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------
    def _handle_branch_switch(self, task: str, session_id: Optional[str]) -> Dict[str, Any]:
        branch = self._extract_branch_name_from_switch(task)
        if not branch:
            return self._error_response("Could not determine which branch to use. Try `/git use develop`.")

        exists, suggestions = self._validate_branch(branch, session_id)
        if not exists:
            message = f"Branch `{branch}` does not exist in this repository."
            if suggestions:
                formatted = ", ".join(f"`{candidate}`" for candidate in suggestions)
                message += f" Did you mean: {formatted}?"
            return self._error_response(message)

        self._set_active_branch(branch, session_id)
        summary = f"Now tracking branch `{branch}` for upcoming /git queries."
        details = "Branch context → session scoped (no local checkout)."
        data = {"active_branch": branch}
        return self._format_response(summary, details, data)

    def _handle_show_branch(self, session_id: Optional[str]) -> Dict[str, Any]:
        branch, is_default = self._get_active_branch(session_id)
        default_branch = self._get_default_branch(session_id)
        summary = f"Currently using branch `{branch}`."
        if is_default:
            summary += " (default branch)"
        details = f"Default branch → `{default_branch}`"
        return self._format_response(summary, details, {"active_branch": branch, "default_branch": default_branch})

    def _handle_repo_info(self, session_id: Optional[str]) -> Dict[str, Any]:
        result = self._execute_git_tool("get_repo_overview", {}, session_id)
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to fetch repo info."))

        repo = result.get("repo") or {}
        summary = f"Repo `{repo.get('full_name') or repo.get('name')}` points to default branch `{repo.get('default_branch')}`."
        lines = [
            f"- Repo → {repo.get('html_url')}",
            f"- Owner → {repo.get('owner')}",
            f"- Visibility → {repo.get('visibility') or ('private' if repo.get('private') else 'public')}",
            f"- Topics → {', '.join(repo.get('topics', [])) or 'n/a'}",
            f"- Last push → {repo.get('pushed_at')}",
        ]
        details = "\n".join(lines)
        return self._format_response(summary, details, {"repo": repo})

    def _handle_list_branches(self, session_id: Optional[str]) -> Dict[str, Any]:
        result = self._execute_git_tool(
            "list_repository_branches",
            {"limit": 100, "names_only": False},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to list branches."))

        branches = result.get("branches", [])
        summary = f"Repo exposes {len(branches)} branch node(s)."
        lines = []
        for branch in branches:
            indicator = "default" if branch.get("is_default") else "branch"
            lines.append(
                f"- {indicator.capitalize()} `{branch.get('name')}` → head {self._short_sha(branch.get('head_sha'))}"
            )
        details = "\n".join(lines)
        return self._format_response(summary, details, {"branches": branches})

    def _handle_recent_commits(
        self,
        session_id: Optional[str],
        *,
        limit: int = 5,
        since: Optional[str] = None,
        author: Optional[str] = None,
        path: Optional[str] = None,
        message_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        branch, used_default = self._get_active_branch(session_id)
        params = {
            "branch": branch,
            "limit": limit,
            "since": since,
            "author": author,
            "path": path,
            "message_query": message_query,
            "include_files": False,
        }
        result = self._execute_git_tool("list_branch_commits", params, session_id)
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to list commits."))

        commits = result.get("commits", [])
        if not commits:
            return self._format_response(
                f"No commits matched on `{branch}`.",
                "Try widening the time range or removing filters.",
                {"branch": branch, "commits": []},
            )

        filter_bits = []
        if author:
            filter_bits.append(f"author {author}")
        if since:
            filter_bits.append(f"since {since}")
        if path:
            filter_bits.append(f"path {path}")
        if message_query:
            filter_bits.append(f"message contains '{message_query}'")
        filters_text = f" with filters ({', '.join(filter_bits)})" if filter_bits else ""
        context_text = " (default branch)" if used_default else ""
        summary = f"{len(commits)} commit node(s) on `{branch}`{context_text}{filters_text}."
        lines = self._format_commit_lines(commits)
        data = {"branch": branch, "commits": commits, "filters": filter_bits}
        return self._format_response(summary, "\n".join(lines), data)

    def _handle_last_commit(self, session_id: Optional[str]) -> Dict[str, Any]:
        return self._handle_recent_commits(session_id, limit=1)

    def _handle_commit_details(
        self,
        sha: str,
        *,
        include_files: bool,
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        result = self._execute_git_tool(
            "get_commit_details",
            {"sha": sha, "include_files": include_files},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to fetch commit."))

        commit = result.get("commit") or {}
        summary = (
            f"Commit `{commit.get('short_sha')}` by {commit.get('author')} "
            f"on {commit.get('date')} touches {len(commit.get('files', [])) if include_files else '0'} file(s)."
        )
        lines = [
            f"- Message → {commit.get('message')}",
            f"- URL → {commit.get('url')}",
        ]
        if include_files:
            lines.append("Changed files:")
            lines.extend(self._format_file_lines(commit.get("files", [])))
        return self._format_response(summary, "\n".join(lines), {"commit": commit})

    def _handle_last_commit_files(self, session_id: Optional[str]) -> Dict[str, Any]:
        branch, _ = self._get_active_branch(session_id)
        result = self._execute_git_tool(
            "list_branch_commits",
            {"branch": branch, "limit": 1, "include_files": True},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to fetch commits."))

        commits = result.get("commits", [])
        if not commits:
            return self._error_response("No commits found on the active branch.")

        commit = commits[0]
        summary = (
            f"Latest commit `{commit.get('short_sha')}` on `{branch}` touches "
            f"{len(commit.get('files', []))} file(s)."
        )
        lines = self._format_file_lines(commit.get("files", []))
        return self._format_response(summary, "\n".join(lines), {"commits": commits, "branch": branch})

    def _handle_commit_files(self, sha: str, session_id: Optional[str]) -> Dict[str, Any]:
        return self._handle_commit_details(sha, include_files=True, session_id=session_id)

    def _handle_file_history(self, path: str, session_id: Optional[str]) -> Dict[str, Any]:
        branch, _ = self._get_active_branch(session_id)
        result = self._execute_git_tool(
            "list_file_history",
            {"path": path, "branch": branch, "limit": 10},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to fetch file history."))

        commits = result.get("commits", [])
        if not commits:
            return self._format_response(
                f"No commits recently touched `{path}` on `{branch}`.",
                "",
                {"path": path, "branch": branch, "commits": []},
            )

        summary = f"File `{path}` was last updated by `{commits[0].get('author')}` in `{commits[0].get('short_sha')}`."
        lines = self._format_commit_lines(commits)
        return self._format_response(summary, "\n".join(lines), {"path": path, "commits": commits})

    def _handle_commit_search(self, keyword: Optional[str], session_id: Optional[str]) -> Dict[str, Any]:
        if not keyword:
            return self._error_response("Provide a keyword, e.g., `/git search commits for 'VAT'`.")

        branch, _ = self._get_active_branch(session_id)
        result = self._execute_git_tool(
            "search_branch_commits",
            {"keyword": keyword, "branch": branch, "limit": 20},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to search commits."))

        commits = result.get("commits", [])
        if not commits:
            return self._format_response(
                f"No commits mention '{keyword}' on `{branch}`.",
                "",
                {"keyword": keyword, "commits": []},
            )

        summary = f"{len(commits)} commit(s) mention '{keyword}' on `{branch}`."
        lines = self._format_commit_lines(commits)
        return self._format_response(summary, "\n".join(lines), {"keyword": keyword, "commits": commits})

    def _handle_compare_refs(self, base_ref: str, head_ref: str, session_id: Optional[str]) -> Dict[str, Any]:
        result = self._execute_git_tool(
            "compare_git_refs",
            {"base_ref": base_ref, "head_ref": head_ref},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to compare refs."))

        comparison = result.get("comparison", {})
        ahead = comparison.get("ahead_by", 0)
        behind = comparison.get("behind_by", 0)
        summary = (
            f"Ref `{comparison.get('head_ref')}` is {ahead} commit(s) ahead "
            f"and {behind} behind `{comparison.get('base_ref')}`."
        )
        commit_lines = self._format_commit_lines(comparison.get("commits", []))
        file_lines = self._format_file_lines(comparison.get("files", []))
        details = "\n".join(["Commits:"] + commit_lines + ["Files:"] + file_lines) if commit_lines or file_lines else ""
        return self._format_response(summary, details, comparison)

    def _handle_list_tags(self, session_id: Optional[str]) -> Dict[str, Any]:
        result = self._execute_git_tool(
            "list_repository_tags",
            {"limit": 25},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to list tags."))

        tags = result.get("tags", [])
        if not tags:
            return self._format_response("Repo has no tags.", "", {"tags": []})

        summary = f"{len(tags)} tag(s) found. Latest tag `{tags[0].get('name')}` points to {self._short_sha(tags[0].get('commit_sha'))}."
        lines = [
            f"- Tag `{tag.get('name')}` → commit {self._short_sha(tag.get('commit_sha'))} ({tag.get('commit_date')})"
            for tag in tags
        ]
        return self._format_response(summary, "\n".join(lines), {"tags": tags})

    def _handle_latest_tag(self, session_id: Optional[str]) -> Dict[str, Any]:
        result = self._execute_git_tool("get_latest_repo_tag", {}, session_id)
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to fetch latest tag."))

        tag = result.get("tag")
        if not tag:
            return self._format_response("Repo has no tags.", "", {"tags": []})

        summary = f"Latest tag `{tag.get('name')}` points to commit {self._short_sha(tag.get('commit_sha'))}."
        details = f"- Commit date → {tag.get('commit_date')}\n- Tarball → {tag.get('tarball_url')}"
        return self._format_response(summary, details, {"tag": tag})

    def _handle_branch_prs(self, task: str, session_id: Optional[str]) -> Dict[str, Any]:
        branch = self._extract_branch_name(task) or self._get_active_branch(session_id)[0]
        state = "open"
        if "closed" in task.lower():
            state = "closed"

        result = self._execute_git_tool(
            "list_branch_pull_requests",
            {"branch": branch, "state": state, "limit": 20, "match_head": False},
            session_id,
        )
        if result.get("error"):
            return self._error_response(result.get("error_message", "Failed to list PRs."))

        prs = result.get("prs", [])
        if not prs:
            return self._format_response(f"No {state} PRs targeting `{branch}`.", "", {"prs": [], "branch": branch})

        summary = f"{len(prs)} {state} PR(s) target branch `{branch}`."
        lines = [
            f"- PR #{pr['number']} by {pr['author']} → `{pr['title']}` (head {pr.get('head_branch')})"
            for pr in prs
        ]
        return self._format_response(summary, "\n".join(lines), {"prs": prs, "branch": branch, "state": state})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _format_response(
        self,
        summary: str,
        details: str,
        data: Dict[str, Any],
        status: str = "success",
        *,
        response_type: str = "git_response",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = dict(data or {})
        if self._last_tool_source and "source" not in payload:
            payload["source"] = self._last_tool_source
        payload.setdefault("token_configured", self.github_token_configured)
        self._last_tool_source = None
        response = {
            "type": response_type,
            "status": status,
            "message": summary,
            "details": details,
            "data": payload,
        }
        if extra:
            response.update({k: v for k, v in extra.items() if v is not None})
        self._attach_plan_metadata(response)
        self._maybe_attach_debug_block(response)
        return response

    def _error_response(self, message: str) -> Dict[str, Any]:
        payload = {"token_configured": self.github_token_configured}
        response = {
            "type": "git_response",
            "status": "error",
            "message": message,
            "details": "",
            "data": payload,
            "error": True,
        }
        self._attach_plan_metadata(response)
        self._maybe_attach_debug_block(response)
        return response

    def _get_git_agent(self):
        if self._git_agent is None:
            from .git_agent import GitAgent

            self._git_agent = GitAgent(self.config)
        return self._git_agent

    def _execute_git_tool(self, tool_name: str, params: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        if self.graph_only_mode and self._tool_requires_live_github(tool_name):
            logger.info(
                "[SLASH GIT] Blocked live Git tool '%s' in graph-only mode (params=%s)",
                tool_name,
                params,
            )
            return {
                "error": True,
                "error_type": "LiveGitDisabled",
                "error_message": (
                    "Live GitHub tools are disabled in graph-only mode. "
                    "Run the ingest workflow to refresh the graph cache."
                ),
            }
        try:
            logger.info("[SLASH GIT] Executing %s with params=%s", tool_name, params)
            result = self.registry.execute_tool(tool_name, params, session_id=session_id)
            if not isinstance(result, Dict):
                raise ValueError(f"{tool_name} returned non-dict response")
            if result.get("error") and result.get("error_type") == "ToolNotFound":
                logger.warning(
                    "[SLASH GIT] Tool %s missing from registry; attempting direct GitAgent fallback",
                    tool_name,
                )
                if self.graph_only_mode:
                    return {
                        "error": True,
                        "error_type": "LiveGitDisabled",
                        "error_message": (
                            "Live GitHub fallback disabled in graph-only mode. "
                            "Please run ingest to refresh the graph before retrying."
                        ),
                    }
                fallback_agent = self._get_git_agent()
                result = fallback_agent.execute(tool_name, params)
            self._last_tool_source = result.get("source")
            self._log_tool_result(tool_name, result)
            return result
        except Exception as exc:
            logger.exception(f"[SLASH GIT] Tool {tool_name} failed: {exc}")
            self._last_tool_source = None
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
            }

    def _tool_requires_live_github(self, tool_name: str) -> bool:
        return tool_name in self.GRAPH_ONLY_BLOCKED_TOOLS

    def _log_tool_result(self, tool_name: str, result: Dict[str, Any]) -> None:
        source = result.get("source") or "unknown"
        count = result.get("count")
        if count is None:
            for key in ("commits", "prs", "branches", "tags"):
                payload = result.get(key)
                if isinstance(payload, list):
                    count = len(payload)
                    break
        logger.info(
            "[SLASH GIT] Tool %s completed (count=%s, source=%s, error=%s)",
            tool_name,
            count if count is not None else "n/a",
            source,
            bool(result.get("error")),
        )

    def _get_active_branch(self, session_id: Optional[str]) -> Tuple[str, bool]:
        branch = None
        if self.session_manager and session_id:
            memory = self.session_manager.get_or_create_session(session_id)
            branch = memory.get_context(self.CONTEXT_KEY)
        if branch:
            return branch, False
        default_branch = self._get_default_branch(session_id)
        return default_branch, True

    def _set_active_branch(self, branch: str, session_id: Optional[str]) -> None:
        if self.session_manager and session_id:
            memory = self.session_manager.get_or_create_session(session_id)
            memory.set_context(self.CONTEXT_KEY, branch)

    def _get_default_branch(self, session_id: Optional[str]) -> str:
        if self._default_branch_cache:
            return self._default_branch_cache

        # Try config fallback before hitting tool
        config_branch = (self.config.get("github") or {}).get("base_branch")
        if config_branch:
            self._default_branch_cache = config_branch

        if self._repo_identifier:
            resolved = resolve_repo_branch(
                self._repo_identifier,
                fallback_branch=self._default_branch_cache or "main",
            )
            if resolved:
                self._default_branch_cache = resolved

        result = self._execute_git_tool("get_repo_overview", {}, session_id)
        if not result.get("error"):
            repo = result.get("repo") or {}
            self._default_branch_cache = repo.get("default_branch") or self._default_branch_cache or "main"
        return self._default_branch_cache or "main"

    def _validate_branch(self, branch: str, session_id: Optional[str]) -> Tuple[bool, List[str]]:
        suggestions: List[str] = []
        repo_id = self._repo_identifier
        if self.metadata_service and repo_id:
            candidates = self.metadata_service.list_branches(repo_id, prefix=branch, limit=50)
            for candidate in candidates:
                if candidate.name.lower() == branch.lower():
                    return True, []
            suggestions = self.metadata_service.suggest_branches(repo_id, branch, limit=5)

        result = self._execute_git_tool(
            "list_repository_branches",
            {"limit": 200, "names_only": True},
            session_id,
        )
        if result.get("error"):
            return False, suggestions
        branches = result.get("branches", [])
        for candidate in branches:
            if isinstance(candidate, str) and candidate.lower() == branch.lower():
                return True, []
        if not suggestions and branches:
            close = difflib.get_close_matches(branch, branches, n=5, cutoff=0.55)
            suggestions = close
        return False, suggestions

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    def _looks_like_branch_switch(self, task: str) -> bool:
        lower = task.lower()
        return lower.startswith(("use ", "switch", "track ")) or " use branch " in lower or lower.startswith("set branch ")

    def _looks_like_branch_query(self, lower: str) -> bool:
        question_phrases = [
            "which branch",
            "what branch",
            "current branch",
            "active branch",
        ]
        return any(phrase in lower for phrase in question_phrases)

    def _extract_branch_name_from_switch(self, task: str) -> Optional[str]:
        match = re.search(r'(?:use|switch(?:\s+to)?|set|track)\s+(?:branch\s+)?(.+)', task, re.IGNORECASE)
        if not match:
            return None
        return self._clean_ref(match.group(1))

    def _extract_branch_name(self, task: str) -> Optional[str]:
        match = re.search(r'(?:branch|prs?|pull requests?)\s+(?:for|on|into)\s+([^\s,]+)', task, re.IGNORECASE)
        if match:
            return self._clean_ref(match.group(1))
        quoted = re.search(r'["\']([^"\']+)["\']', task)
        if quoted:
            return self._clean_ref(quoted.group(1))
        return None

    def _extract_sha(self, task: str) -> Optional[str]:
        match = re.search(r'\b[0-9a-f]{7,40}\b', task, re.IGNORECASE)
        return match.group(0) if match else None

    def _extract_limit(self, task: str) -> Optional[int]:
        match = re.search(r'last\s+(\d+)\s+commits?', task, re.IGNORECASE)
        if match:
            return max(1, min(int(match.group(1)), 50))
        return None

    def _extract_since_timestamp(self, task: str) -> Optional[str]:
        lower = task.lower()
        now = datetime.now(timezone.utc)
        if "since yesterday" in lower or "yesterday" in lower:
            return (now - timedelta(days=1)).isoformat()
        if "since today" in lower or "today" in lower:
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        if "this week" in lower:
            start_of_week = now - timedelta(days=now.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            return start_of_week.isoformat()
        match_days = re.search(r'last\s+(\d+)\s+days', lower)
        if match_days:
            return (now - timedelta(days=int(match_days.group(1)))).isoformat()
        match_hours = re.search(r'last\s+(\d+)\s+hours', lower)
        if match_hours:
            return (now - timedelta(hours=int(match_hours.group(1)))).isoformat()
        match_since = re.search(r'since\s+([^\s]+)', lower)
        if match_since and match_since.group(1) not in {"yesterday", "today"}:
            # Basic ISO passthrough
            return match_since.group(1)
        return None

    def _extract_author(self, task: str) -> Optional[str]:
        match = re.search(r'commits?\s+by\s+([^\s,]+)', task, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_file_path(self, task: str) -> Optional[str]:
        quoted = re.search(r'["\']([^"\']+\.[^"\']+)["\']', task)
        if quoted:
            return quoted.group(1)
        slash_path = re.search(r'(\S+/\S+)', task)
        if slash_path:
            return slash_path.group(1)
        dot_path = re.search(r'\b(\w+\.[a-z0-9]{2,})\b', task, re.IGNORECASE)
        if dot_path:
            return dot_path.group(1)
        match = re.search(r'history of ([^\s,]+)', task, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_search_keyword(self, task: str) -> Optional[str]:
        quoted = re.search(r'["\']([^"\']+)["\']', task)
        if quoted:
            return quoted.group(1)
        match = re.search(r'(?:search commits for|commits mentioning)\s+(.+)', task, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_ref_pair(self, task: str) -> Optional[Tuple[str, str]]:
        match = re.search(r'(?:diff|compare)\s+(?:between\s+)?([^\s]+)\s+(?:and|vs)\s+([^\s]+)', task, re.IGNORECASE)
        if match:
            return self._clean_ref(match.group(1)), self._clean_ref(match.group(2))
        ahead_match = re.search(r'([^\s]+)\s+(?:ahead|behind)\s+of\s+([^\s]+)', task, re.IGNORECASE)
        if ahead_match:
            head = self._clean_ref(ahead_match.group(1))
            base = self._clean_ref(ahead_match.group(2))
            return base, head
        return None

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_commit_lines(self, commits: List[Dict[str, Any]]) -> List[str]:
        lines = []
        for commit in commits:
            sha = commit.get("short_sha") or commit.get("sha")
            author = commit.get("author") or "unknown"
            timestamp = commit.get("timestamp") or commit.get("date") or "unknown time"
            headline = self._first_line(commit.get("message"))
            link = commit.get("url") or self._build_commit_url(commit, commit.get("repo_url"), commit.get("sha"))
            if link:
                lines.append(f"- `{sha}` by {author} ({timestamp}) → {headline} · {link}")
            else:
                lines.append(f"- `{sha}` by {author} ({timestamp}) → {headline}")
        return lines

    def _format_file_lines(self, files: List[Dict[str, Any]]) -> List[str]:
        lines = []
        for file in files or []:
            lines.append(
                f"- {file.get('filename')} → {file.get('status')} (+{file.get('additions', 0)}/-{file.get('deletions', 0)})"
            )
        return lines

    def _short_sha(self, sha: Optional[str]) -> str:
        return sha[:7] if sha else ""

    def _first_line(self, text: Optional[str]) -> str:
        return (text or "").splitlines()[0][:120]

    def _clean_ref(self, ref: str) -> str:
        return ref.strip().strip('`"\'').rstrip(",.")

    def _repo_html_url(self, plan: GitQueryPlan) -> Optional[str]:
        repo = plan.repo
        if repo and repo.repo_owner and repo.repo_name:
            return f"https://github.com/{repo.repo_owner}/{repo.repo_name}"
        return None

    def _build_commit_url(self, commit: Dict[str, Any], repo_url: Optional[str], sha: Optional[str]) -> Optional[str]:
        if commit.get("url"):
            return commit["url"]
        base = commit.get("repo_url") or repo_url
        if base and sha:
            return f"{base.rstrip('/')}/commit/{sha}"
        return base

    def _build_pr_url(self, pr: Dict[str, Any], repo_url: Optional[str], number: Optional[Any]) -> Optional[str]:
        if pr.get("url"):
            return pr["url"]
        base = pr.get("repo_url") or repo_url
        if base and number:
            return f"{base.rstrip('/')}/pull/{number}"
        return base

    # ------------------------------------------------------------------
    # Pipeline helpers
    # ------------------------------------------------------------------
    def _maybe_run_git_pipeline(
        self,
        task: str,
        lower: str,
        *,
        plan: Optional[SlashQueryPlan] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.git_pipeline:
            return None
        if self._looks_like_branch_switch(task) or self._looks_like_branch_query(lower):
            return None
        if not self._should_use_pipeline(lower, plan):
            return None
        try:
            result = self.git_pipeline.run(task)
        except Exception as exc:
            logger.warning("[SLASH GIT] Pipeline execution failed: %s", exc)
            return None
        if not result:
            return None
        return self._format_pipeline_response(result)

    def _should_use_pipeline(self, lower: str, plan: Optional[SlashQueryPlan] = None) -> bool:
        control_keywords = (
            "list ",
            "show ",
            "compare",
            "diff",
            "tag",
            "tags",
        )
        if lower.startswith(control_keywords):
            return False

        recent_commit_keywords = (
            "last commit",
            "latest commit",
            "recent commit",
        )
        if any(keyword in lower for keyword in recent_commit_keywords):
            return False

        trigger_keywords = (
            "what",
            "changed",
            "happened",
            "summarize",
            "summary",
            "bug",
            "issue",
            "fix",
            "last ",
            "this week",
            "component",
            "activity",
        )
        if any(keyword in lower for keyword in trigger_keywords):
            return True
        if not plan:
            return False
        if plan.targets:
            return True
        if plan.intent in {
            SlashQueryIntent.SUMMARIZE,
            SlashQueryIntent.STATUS,
            SlashQueryIntent.INVESTIGATE,
        }:
            return True
        return False

    def _format_pipeline_response(self, result: SlashGitPipelineResult) -> Dict[str, Any]:
        plan = result.plan
        snapshot = result.snapshot
        commits = snapshot.get("commits", [])
        prs = snapshot.get("prs", [])
        summary = self._build_pipeline_summary(plan, commits, prs)

        graph_context = self._build_pipeline_graph_context(plan, snapshot)
        analysis_payload = None
        if self.git_formatter:
            analysis_payload, error = self.git_formatter.generate(plan, snapshot, graph=graph_context)
            if error:
                logger.warning("[SLASH GIT] Formatter failed, falling back to basic summary: %s", error)
        detail_lines: List[str]
        if analysis_payload:
            detail_lines = self._format_analysis_sections(analysis_payload)
            summary = analysis_payload.get("summary") or summary
        else:
            detail_lines = self._fallback_snapshot_details(commits, prs)

        plan_payload = {
            "mode": plan.mode.value,
            "repo_id": plan.repo_id,
            "component_id": plan.component_id,
            "time_window": plan.time_window.to_dict() if plan.time_window else None,
            "authors": plan.authors,
            "labels": plan.labels,
            "topic": plan.topic,
        }

        context = self._build_git_context(plan, graph_context)
        sources = self._build_git_sources(plan, commits, prs)

        data = {
            "plan": plan_payload,
            "snapshot": snapshot,
            "graph_context": graph_context,
            "analysis": analysis_payload,
        }
        self._last_tool_source = "slash_git_pipeline"
        self._enqueue_impact_job(plan, snapshot, analysis_payload)
        extra_fields: Dict[str, Any] = {
            "context": context,
            "sources": sources,
        }
        if analysis_payload:
            extra_fields.update(
                {
                    "analysis": analysis_payload,
                    "sections": analysis_payload.get("sections"),
                    "notable_prs": analysis_payload.get("notable_prs"),
                    "breaking_changes": analysis_payload.get("breaking_changes"),
                    "next_actions": analysis_payload.get("next_actions"),
                    "references": analysis_payload.get("references"),
                }
            )
        return self._format_response(
            summary,
            "\n".join(detail_lines),
            data,
            response_type="slash_git_summary",
            extra=extra_fields,
        )

    def _format_analysis_sections(self, analysis: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        for section in analysis.get("sections", []):
            title = section.get("title") or "Insights"
            lines.append(f"{title}:")
            for insight in section.get("insights", []):
                lines.append(f"- {insight}")
        if not lines:
            lines.append("No structured insights were produced.")
        return lines

    def _fallback_snapshot_details(self, commits: List[Dict[str, Any]], prs: List[Dict[str, Any]]) -> List[str]:
        detail_lines: List[str] = []
        if commits:
            detail_lines.append("Commits:")
            detail_lines.extend(self._format_commit_lines(commits[:5]))
        if prs:
            detail_lines.append("PRs:")
            detail_lines.extend(self._format_pr_lines(prs[:5]))
        if not detail_lines:
            detail_lines.append("No relevant activity in the selected window.")
        return detail_lines

    def _build_git_context(self, plan: GitQueryPlan, graph_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        repo_label = plan.repo.name if plan.repo else (plan.repo_id or self._repo_identifier or "repository")
        component_label = plan.component.name if plan.component else None
        time_window_label = plan.time_window.label if plan.time_window else "recent activity"
        mode = plan.mode.value if plan.mode else None
        scope = repo_label
        if component_label:
            scope = f"{repo_label} · {component_label}"

        context: Dict[str, Any] = {
            "repo_label": repo_label,
            "component_label": component_label,
            "scope_label": scope,
            "time_window_label": time_window_label,
            "mode": mode,
        }
        if graph_context:
            context["graph_counts"] = graph_context.get("activity_counts")
            context["authors"] = graph_context.get("authors")
            context["top_files"] = graph_context.get("top_files")
        return context

    def _build_git_sources(
        self,
        plan: GitQueryPlan,
        commits: List[Dict[str, Any]],
        prs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        repo_label = plan.repo.name if plan.repo else (plan.repo_id or self._repo_identifier or "repository")
        repo_url = self._repo_html_url(plan)
        repo_id = plan.repo_id or self._repo_identifier
        component_label = plan.component.name if plan.component else None

        for idx, commit in enumerate(commits):
            sha = commit.get("sha") or commit.get("commit_sha") or commit.get("id")
            short_sha = commit.get("short_sha") or self._short_sha(sha)
            commit_url = commit.get("url") or self._build_commit_url(commit, repo_url, sha)
            evidence_id = git_commit_evidence_id(repo_id, sha) if repo_id and sha else None
            sources.append(
                {
                    "id": evidence_id or sha or f"commit-{idx}",
                    "type": "commit",
                    "rank": idx + 1,
                    "repo": repo_id,
                    "repo_label": repo_label,
                    "component_label": component_label,
                    "short_sha": short_sha,
                    "author": commit.get("author"),
                    "timestamp": commit.get("timestamp") or commit.get("date"),
                    "message": commit.get("message"),
                    "url": commit_url,
                    "files_changed": commit.get("files_changed"),
                    "labels": commit.get("labels"),
                    "service_ids": commit.get("service_ids"),
                    "component_ids": commit.get("component_ids") or ([plan.component_id] if plan.component_id else None),
                }
            )

        for idx, pr in enumerate(prs):
            number = pr.get("number") or pr.get("pr_number")
            pr_url = pr.get("url") or self._build_pr_url(pr, repo_url, number)
            evidence_id = git_pr_evidence_id(repo_id, number) if repo_id and number else None
            sources.append(
                {
                    "id": evidence_id or number or f"pr-{idx}",
                    "type": "pr",
                    "rank": len(commits) + idx + 1,
                    "repo": repo_id,
                    "repo_label": repo_label,
                    "component_label": component_label,
                    "pr_number": number,
                    "title": pr.get("title"),
                    "author": pr.get("author"),
                    "timestamp": pr.get("timestamp") or pr.get("merged_at") or pr.get("updated_at"),
                    "url": pr_url,
                    "state": pr.get("state"),
                    "merged": pr.get("merged"),
                    "head_branch": pr.get("head_branch"),
                    "base_branch": pr.get("base_branch"),
                    "labels": pr.get("labels"),
                    "files_changed": pr.get("files_changed"),
                    "component_ids": pr.get("component_ids") or ([plan.component_id] if plan.component_id else None),
                }
            )

        return sources

    def _build_pipeline_summary(self, plan: GitQueryPlan, commits: List[Dict[str, Any]], prs: List[Dict[str, Any]]) -> str:
        repo_label = plan.repo.name if plan.repo else (plan.repo_id or "repository")
        component_label = plan.component.name if plan.component else None
        window_label = plan.time_window.label if plan.time_window else "recently"
        commit_count = len(commits)
        pr_count = len(prs)
        scope = f"{repo_label}"
        if component_label:
            scope = f"{repo_label} · {component_label}"

        if commit_count == 0 and pr_count == 0:
            return f"No matching activity for {scope} {window_label}."

        parts = [f"{scope} saw"]
        if commit_count:
            parts.append(f"{commit_count} commit{'s' if commit_count != 1 else ''}")
        if pr_count:
            if commit_count:
                parts.append("and")
            parts.append(f"{pr_count} PR{'s' if pr_count != 1 else ''}")
        parts.append(f"{window_label}.")
        return " ".join(parts)

    def _build_pipeline_graph_context(self, plan: GitQueryPlan, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        commits = snapshot.get("commits") or []
        prs = snapshot.get("prs") or []
        events = commits + prs
        if not events:
            context = {}
        else:
            def _collect(key: str) -> List[str]:
                values = set()
                for item in events:
                    for value in item.get(key) or []:
                        if value:
                            values.add(value)
                return sorted(values)

            services = _collect("service_ids")
            components = _collect("component_ids")
            apis = _collect("changed_apis")
            labels = _collect("labels")
            authors = sorted({item.get("author") for item in events if item.get("author")})

            file_counter: Counter[str] = Counter()
            for item in events:
                for file_path in item.get("files_changed") or []:
                    if file_path:
                        file_counter[file_path] += 1
            top_files = [
                {"path": path, "touches": count}
                for path, count in file_counter.most_common(5)
            ]

            incident_signals: List[Dict[str, str]] = []
            incident_keywords = ("incident", "sev", "pager", "rollback", "hotfix")
            for item in events:
                source = "pr" if item.get("pr_number") is not None else "commit"
                reference = str(
                    item.get("pr_number")
                    or item.get("commit_sha")
                    or item.get("sha")
                    or item.get("id")
                    or ""
                )
                normalized_labels = [label.lower() for label in item.get("labels", []) if isinstance(label, str)]
                label_hit = next(
                    (label for label in normalized_labels if label.startswith("incident") or label.startswith("sev")),
                    None,
                )
                message_blob = (item.get("message") or item.get("title") or "").lower()
                if label_hit:
                    incident_signals.append({"source": source, "reference": reference, "reason": f"label:{label_hit}"})
                elif any(keyword in message_blob for keyword in incident_keywords):
                    incident_signals.append({"source": source, "reference": reference, "reason": "message"})
                if len(incident_signals) >= 5:
                    break

            context = {
                "services": services,
                "components": components,
                "apis": apis,
                "labels": labels,
                "authors": authors,
                "top_files": top_files,
                "incident_signals": incident_signals,
            }

        activity_counts = {"commits": len(commits), "prs": len(prs)}
        branch = plan.repo.default_branch if plan.repo else None
        time_window_label = plan.time_window.label if plan.time_window else None

        graph_context = {
            "repo_id": plan.repo_id,
            "component_id": plan.component_id,
            "activity_counts": activity_counts,
            "branch": branch,
            "time_window": time_window_label,
        }
        graph_context.update(context)
        return {key: value for key, value in graph_context.items() if value not in (None, [], {})}

    def _format_pr_lines(self, prs: List[Dict[str, Any]]) -> List[str]:
        lines = []
        for pr in prs:
            number = pr.get("number")
            title = pr.get("title") or ""
            author = pr.get("author") or "unknown"
            link = pr.get("url") or self._build_pr_url(pr, pr.get("repo_url"), number)
            if link:
                lines.append(f"- PR #{number} by {author} → {title} · {link}")
            else:
                lines.append(f"- PR #{number} by {author} → {title}")
        return lines

    def _enqueue_impact_job(
        self,
        plan: GitQueryPlan,
        snapshot: Dict[str, Any],
        analysis_payload: Optional[Dict[str, Any]],
    ) -> None:
        if not self.impact_auto_enabled or not self.impact_endpoint_base:
            return
        payload = self._build_impact_payload(plan, snapshot, analysis_payload)
        if not payload:
            return
        logger.info(
            "[SLASH GIT] Enqueuing auto-impact job for %s (commits=%s)",
            payload.get("repo"),
            ", ".join(payload.get("commits") or []) or "files",
        )
        thread = threading.Thread(
            target=self._post_impact_payload,
            args=(payload,),
            daemon=True,
        )
        thread.start()

    def _build_impact_payload(
        self,
        plan: GitQueryPlan,
        snapshot: Dict[str, Any],
        analysis_payload: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        repo_full = None
        if plan.repo and getattr(plan.repo, "repo_owner", None) and getattr(plan.repo, "repo_name", None):
            repo_full = f"{plan.repo.repo_owner}/{plan.repo.repo_name}"
        repo_full = repo_full or plan.repo_id or self._repo_identifier
        if not repo_full:
            return None

        commits = snapshot.get("commits") or []
        prs = snapshot.get("prs") or []
        commit_shas = [
            entry.get("sha") or entry.get("commit_sha")
            for entry in commits
            if entry.get("sha") or entry.get("commit_sha")
        ]
        commit_shas = [sha for sha in commit_shas if sha][:5]

        file_changes: List[Dict[str, str]] = []
        if not commit_shas:
            for entry in commits:
                for path in entry.get("files_changed") or []:
                    file_changes.append({"path": path, "change_type": "modified"})
            if not file_changes:
                for pr in prs:
                    for path in pr.get("files_changed") or []:
                        file_changes.append({"path": path, "change_type": "modified"})
            file_changes = file_changes[:20]

        if not commit_shas and not file_changes:
            return None

        title_component = plan.component.name if plan.component else plan.repo.name if plan.repo else plan.repo_id
        title = f"/git auto-impact · {title_component or repo_full}"
        description = analysis_payload.get("summary") if analysis_payload else None

        payload: Dict[str, Any] = {
            "repo": repo_full,
            "title": title,
            "description": description,
        }
        if commit_shas:
            payload["commits"] = commit_shas
        else:
            payload["files"] = file_changes
        return payload

    def _post_impact_payload(self, payload: Dict[str, Any]) -> None:
        try:
            endpoint = f"{self.impact_endpoint_base.rstrip('/')}/impact/git-change"
            response = httpx.post(endpoint, json=payload, timeout=2.5)
            if response.status_code >= 400:
                logger.debug(
                    "[SLASH GIT] Auto impact request failed (status=%s): %s",
                    response.status_code,
                    response.text[:200],
                )
            else:
                logger.info(
                    "[SLASH GIT] Auto-impact git-change recorded (repo=%s, commits=%d, files=%d)",
                    payload.get("repo"),
                    len(payload.get("commits") or []),
                    len(payload.get("files") or []),
                )
        except Exception as exc:
            logger.debug("[SLASH GIT] Auto impact request error: %s", exc)

    # ------------------------------------------------------------------
    # Debug block helpers
    # ------------------------------------------------------------------
    def _maybe_attach_debug_block(self, response: Dict[str, Any]) -> None:
        if not self.debug_block_enabled:
            return
        if response.get("error"):
            # Surface debug info only for successful flows to avoid leaking errors
            return
        debug_block = self._build_debug_block(response)
        if not debug_block:
            return
        response["debug"] = debug_block
        if response.get("type") != "slash_git_summary":
            response["message"] = self._append_json_block(response.get("message"), debug_block)

    def _attach_plan_metadata(self, response: Dict[str, Any]) -> None:
        if not self._active_query_plan:
            return
        metadata = response.setdefault("metadata", {})
        metadata["query_plan"] = self._active_query_plan

    def _build_debug_block(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = response.get("data") or {}
        source = data.get("source") or self._last_tool_source or self.debug_source_label
        collection_keys = ("commits", "prs", "branches", "tags", "files")
        evidence_items = None
        for key in collection_keys:
            candidate = data.get(key)
            if isinstance(candidate, list) and candidate:
                evidence_items = candidate
                break
        if not evidence_items:
            singleton = data.get("repo") or data.get("commit") or data.get("tag")
            if singleton:
                evidence_items = [singleton]

        retrieved_count = len(evidence_items) if evidence_items else 0
        sample_evidence: List[Dict[str, Any]] = []
        if evidence_items:
            first_item = evidence_items[0]
            snippet_text = first_item.get("message") or first_item.get("title") or first_item.get("summary") or ""
            snippet = self._clean_snippet(snippet_text)
            if snippet:
                sample_evidence.append(
                    {
                        "repo": first_item.get("repo")
                        or first_item.get("repository")
                        or data.get("repo_name")
                        or self.debug_repo_label,
                        "message": snippet,
                    }
                )

        status = response.get("status") or ("PASS" if retrieved_count > 0 else "WARN")
        if status.lower() == "success" and retrieved_count == 0:
            status = "WARN"
        elif status.lower() != "success":
            status = status.upper()

        return {
            "source": source,
            "retrieved_count": retrieved_count,
            "sample_evidence": sample_evidence,
            "status": status if isinstance(status, str) else "PASS",
        }

    @staticmethod
    def _append_json_block(message: Optional[str], payload: Dict[str, Any]) -> str:
        block_text = json.dumps(payload, ensure_ascii=False)
        formatted = f"```json\n{block_text}\n```"
        if message:
            if block_text in message:
                return message
            return f"{message.rstrip()}\n\n{formatted}"
        return formatted

    @staticmethod
    def _clean_snippet(text: str, *, max_length: int = 160) -> str:
        if not text:
            return ""
        snippet = " ".join(text.strip().split())
        if len(snippet) <= max_length:
            return snippet
        return snippet[: max_length - 3].rstrip() + "..."


