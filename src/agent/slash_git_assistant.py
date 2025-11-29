import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


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

    def __init__(self, agent_registry, session_manager=None, config: Optional[Dict[str, Any]] = None):
        self.registry = agent_registry
        self.session_manager = session_manager
        self.config = config or {}
        self._default_branch_cache: Optional[str] = None
        self._git_agent = None

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    def handle(self, task: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Main entrypoint invoked by the slash command handler."""
        task = (task or "").strip()
        if not task:
            return self._error_response("Please provide a Git question.")

        lower = task.lower()

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

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------
    def _handle_branch_switch(self, task: str, session_id: Optional[str]) -> Dict[str, Any]:
        branch = self._extract_branch_name_from_switch(task)
        if not branch:
            return self._error_response("Could not determine which branch to use. Try `/git use develop`.")

        if not self._branch_exists(branch, session_id):
            return self._error_response(f"Branch `{branch}` does not exist in this repository.")

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
    def _format_response(self, summary: str, details: str, data: Dict[str, Any], status: str = "success") -> Dict[str, Any]:
        return {
            "type": "git_response",
            "status": status,
            "message": summary,
            "details": details,
            "data": data,
        }

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "type": "git_response",
            "status": "error",
            "message": message,
            "details": "",
            "data": {},
            "error": True,
        }

    def _get_git_agent(self):
        if self._git_agent is None:
            from .git_agent import GitAgent

            self._git_agent = GitAgent(self.config)
        return self._git_agent

    def _execute_git_tool(self, tool_name: str, params: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        try:
            result = self.registry.execute_tool(tool_name, params, session_id=session_id)
            if not isinstance(result, Dict):
                raise ValueError(f"{tool_name} returned non-dict response")
            if result.get("error") and result.get("error_type") == "ToolNotFound":
                logger.warning(
                    "[SLASH GIT] Tool %s missing from registry; attempting direct GitAgent fallback",
                    tool_name,
                )
                fallback_agent = self._get_git_agent()
                return fallback_agent.execute(tool_name, params)
            return result
        except Exception as exc:
            logger.exception(f"[SLASH GIT] Tool {tool_name} failed: {exc}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
            }

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

        result = self._execute_git_tool("get_repo_overview", {}, session_id)
        if not result.get("error"):
            repo = result.get("repo") or {}
            self._default_branch_cache = repo.get("default_branch") or self._default_branch_cache or "main"
        return self._default_branch_cache or "main"

    def _branch_exists(self, branch: str, session_id: Optional[str]) -> bool:
        result = self._execute_git_tool(
            "list_repository_branches",
            {"limit": 200, "names_only": True},
            session_id,
        )
        if result.get("error"):
            return False
        branches = result.get("branches", [])
        return branch in branches

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
            lines.append(
                f"- `{commit.get('short_sha') or commit.get('sha')}` "
                f"by {commit.get('author')} ({commit.get('date')}) → {self._first_line(commit.get('message'))}"
            )
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


