"""
GitHub PR/Branch Service - Fetches branch comparisons and file diffs from GitHub API.

Used by the Oqoqo self-evolving docs system to detect when monitored files
(like api_server.py) change in a branch compared to main.
"""

import os
import logging
import base64
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Configuration from environment (with demo-friendly defaults)
# NOTE: All secrets (including GITHUB_TOKEN) must be provided via environment
#       or config and are never hardcoded.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "tiangolo")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME", "fastapi")
GITHUB_MONITORED_FILE = os.getenv("GITHUB_MONITORED_FILE", "fastapi/applications.py")
GITHUB_BASE_BRANCH = os.getenv("GITHUB_BASE_BRANCH", "master")

# Allow overriding GitHub API base for enterprise installs or testing.
GITHUB_API_BASE = os.getenv("GITHUB_API_URL", "https://api.github.com")


@dataclass
class ChangedFile:
    """Represents a file changed in a branch comparison."""
    filename: str
    status: str  # added, removed, modified, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None  # The diff patch if available


@dataclass
class BranchComparison:
    """Result of comparing two branches."""
    base_branch: str
    head_branch: str
    ahead_by: int
    behind_by: int
    status: str  # diverged, ahead, behind, identical
    files: List[ChangedFile]
    total_commits: int
    monitored_file_changed: bool
    monitored_file_patch: Optional[str] = None


class GitHubPRService:
    """
    GitHub API client for branch comparison and file content retrieval.

    Used to detect if monitored files changed in a feature branch vs main.
    Also provides PR listing and details for Git agent tools.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        monitored_file: Optional[str] = None,
        base_branch: Optional[str] = None
    ):
        # Support both config dict and individual parameters for backward compatibility
        if config:
            github_config = config.get("github", {})
            self.token = token or os.getenv("GITHUB_TOKEN") or github_config.get("token", "")
            self.owner = owner or github_config.get("repo_owner", GITHUB_REPO_OWNER)
            self.repo = repo or github_config.get("repo_name", GITHUB_REPO_NAME)
            self.monitored_file = monitored_file or github_config.get("monitored_file", GITHUB_MONITORED_FILE)
            self.base_branch = base_branch or github_config.get("base_branch", GITHUB_BASE_BRANCH)
        else:
            self.token = token or GITHUB_TOKEN
            self.owner = owner or GITHUB_REPO_OWNER
            self.repo = repo or GITHUB_REPO_NAME
            self.monitored_file = monitored_file or GITHUB_MONITORED_FILE
            self.base_branch = base_branch or GITHUB_BASE_BRANCH
        
        # Build base headers for all requests
        github_config = (config or {}).get("github", {}) if config else {}
        user_agent = (
            github_config.get("user_agent")
            or os.getenv("GITHUB_USER_AGENT")
            or "cerebros-slash-git/1.0"
        )
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
            # Required by GitHub and useful for debugging/demo identification.
            "User-Agent": user_agent,
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        
        logger.info(f"[GITHUB PR SERVICE] Initialized for {self.owner}/{self.repo}")
        logger.info(f"[GITHUB PR SERVICE] Monitoring file: {self.monitored_file}")
        logger.info(f"[GITHUB PR SERVICE] Base branch: {self.base_branch}")
        logger.info(f"[GITHUB PR SERVICE] Token configured: {bool(self.token)}")

        self._repo_cache: Optional[Dict[str, Any]] = None
    
    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        *,
        max_retries: int = 2,
    ) -> Any:
        """
        Make an authenticated request to GitHub API.

        All GitHub traffic is backend-only and uses a Personal Access Token (PAT)
        supplied via environment or config. If no token is configured, we fail
        fast with a clear error instead of falling back to anonymous limits.
        """
        if not self.token:
            raise GitHubAPIError(
                "GitHub token not configured. Set GITHUB_TOKEN to enable Git features."
            )

        url = f"{GITHUB_API_BASE}{endpoint}"
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        backoff_seconds = 1.0
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            for attempt in range(max_retries + 1):
                response = client.request(method, url, headers=request_headers, params=params)

                # Fast-path success
                if response.status_code < 400:
                    return response.json()

                # Not found / auth errors are not retried.
                if response.status_code == 404:
                    raise GitHubAPIError(f"Resource not found: {endpoint}")
                if response.status_code == 401:
                    raise GitHubAPIError("Authentication failed. Check GITHUB_TOKEN.")

                # Handle rate limiting with a small exponential backoff for demos.
                if response.status_code == 403:
                    remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
                    reset_at = response.headers.get("X-RateLimit-Reset")
                    logger.warning(
                        "[GITHUB PR SERVICE] 403 from GitHub (remaining=%s, reset_at=%s, attempt=%s)",
                        remaining,
                        reset_at,
                        attempt,
                    )
                    # If we still have attempts left and remaining is not explicitly zero,
                    # backoff briefly and retry; otherwise surface a clear error.
                    if attempt < max_retries and remaining not in {"0", "0.0"}:
                        time.sleep(backoff_seconds)
                        backoff_seconds *= 2
                        continue
                    raise GitHubAPIError(
                        f"Access forbidden. Rate limit remaining: {remaining or 'unknown'}"
                    )

                if response.status_code >= 400:
                    raise GitHubAPIError(
                        f"GitHub API error {response.status_code}: {response.text}"
                    )

            # Defensive fallback; loop should have returned or raised.
            raise GitHubAPIError("Unexpected GitHub API failure after retries.")

    def _repo_endpoint(self, suffix: str) -> str:
        """Helper to build repo-scoped endpoints."""
        return f"/repos/{self.owner}/{self.repo}{suffix}"
    
    def compare_branches(self, head_branch: str, base_branch: Optional[str] = None) -> BranchComparison:
        """
        Compare a feature branch against the base branch.
        
        Args:
            head_branch: The feature branch to compare
            base_branch: The base branch (defaults to configured base_branch)
            
        Returns:
            BranchComparison with list of changed files and metadata
        """
        base = base_branch or self.base_branch
        
        logger.info(f"[GITHUB PR SERVICE] Comparing {base}...{head_branch}")
        
        # GitHub compare API: GET /repos/{owner}/{repo}/compare/{basehead}
        endpoint = f"/repos/{self.owner}/{self.repo}/compare/{base}...{head_branch}"
        
        data = self._make_request(endpoint)
        
        # Parse changed files
        files = []
        monitored_changed = False
        monitored_patch = None
        
        for file_data in data.get("files", []):
            filename = file_data.get("filename", "")
            
            changed_file = ChangedFile(
                filename=filename,
                status=file_data.get("status", "unknown"),
                additions=file_data.get("additions", 0),
                deletions=file_data.get("deletions", 0),
                changes=file_data.get("changes", 0),
                patch=file_data.get("patch"),
            )
            files.append(changed_file)
            
            # Check if this is the monitored file
            if filename == self.monitored_file:
                monitored_changed = True
                monitored_patch = file_data.get("patch")
                logger.info(f"[GITHUB PR SERVICE] Monitored file '{filename}' changed!")
        
        comparison = BranchComparison(
            base_branch=base,
            head_branch=head_branch,
            ahead_by=data.get("ahead_by", 0),
            behind_by=data.get("behind_by", 0),
            status=data.get("status", "unknown"),
            files=files,
            total_commits=data.get("total_commits", 0),
            monitored_file_changed=monitored_changed,
            monitored_file_patch=monitored_patch,
        )
        
        logger.info(f"[GITHUB PR SERVICE] Comparison result: {len(files)} files changed, "
                   f"monitored file changed: {monitored_changed}")
        
        return comparison

    def get_repo_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch repository metadata (cached for repeated lookups).
        """
        if self._repo_cache and not force_refresh:
            return self._repo_cache

        endpoint = self._repo_endpoint("")
        data = self._make_request(endpoint)
        repo_info = {
            "name": data.get("name"),
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "default_branch": data.get("default_branch", self.base_branch),
            "private": data.get("private", False),
            "visibility": data.get("visibility"),
            "html_url": data.get("html_url"),
            "ssh_url": data.get("ssh_url"),
            "clone_url": data.get("clone_url"),
            "pushed_at": data.get("pushed_at"),
            "updated_at": data.get("updated_at"),
            "created_at": data.get("created_at"),
            "topics": data.get("topics", []),
            "owner": data.get("owner", {}).get("login"),
            "open_issues_count": data.get("open_issues_count", 0),
            "forks_count": data.get("forks_count", 0),
            "stargazers_count": data.get("stargazers_count", 0),
            "watchers_count": data.get("subscribers_count") or data.get("watchers_count", 0),
            "license": data.get("license", {}),
        }

        self._repo_cache = repo_info
        return repo_info

    def get_default_branch(self) -> str:
        """Return the repository's default branch."""
        repo_info = self.get_repo_info()
        return repo_info.get("default_branch") or self.base_branch or "main"

    def list_branches(self, names_only: bool = True, limit: int = 100) -> List[Any]:
        """
        List repository branches with optional metadata.
        """
        params = {
            "per_page": max(1, min(limit, 100))
        }
        endpoint = self._repo_endpoint("/branches")
        data = self._make_request(endpoint, params=params)
        default_branch = self.get_default_branch()

        branches: List[Any] = []
        for branch in data:
            branch_info = {
                "name": branch.get("name"),
                "is_default": branch.get("name") == default_branch,
                "protected": branch.get("protected", False),
                "head_sha": (branch.get("commit") or {}).get("sha"),
                "commit_url": (branch.get("commit") or {}).get("html_url"),
            }
            branches.append(branch_info if not names_only else branch_info["name"])

        return branches

    def get_branch(self, branch: str) -> Dict[str, Any]:
        """Get metadata for a single branch."""
        endpoint = self._repo_endpoint(f"/branches/{branch}")
        data = self._make_request(endpoint)
        default_branch = self.get_default_branch()
        return {
            "name": data.get("name"),
            "is_default": data.get("name") == default_branch,
            "protected": data.get("protected", False),
            "head_sha": (data.get("commit") or {}).get("sha"),
            "commit_url": (data.get("commit") or {}).get("html_url"),
        }
    
    def get_file_content(self, ref: str, path: str) -> str:
        """
        Get the content of a file at a specific branch/commit.
        
        Args:
            ref: Branch name or commit SHA
            path: Path to the file in the repo
            
        Returns:
            The file content as a string
        """
        logger.info(f"[GITHUB PR SERVICE] Fetching {path} at ref {ref}")
        
        # GitHub contents API: GET /repos/{owner}/{repo}/contents/{path}?ref={ref}
        endpoint = f"/repos/{self.owner}/{self.repo}/contents/{path}?ref={ref}"
        
        data = self._make_request(endpoint)
        
        # Content is base64 encoded
        content_b64 = data.get("content", "")
        if not content_b64:
            raise GitHubAPIError(f"No content found for {path} at {ref}")
        
        # Decode base64 content
        content = base64.b64decode(content_b64).decode("utf-8")
        
        logger.info(f"[GITHUB PR SERVICE] Retrieved {len(content)} bytes from {path}")
        
        return content
    
    def get_monitored_file_from_branch(self, branch: str) -> str:
        """
        Get the monitored file content from a specific branch.
        
        Args:
            branch: Branch name to fetch from
            
        Returns:
            The file content as a string
        """
        return self.get_file_content(branch, self.monitored_file)
    
    def check_branch_for_api_changes(self, branch: str) -> Dict[str, Any]:
        """
        Check if a branch has changes to the monitored API file.
        
        This is the main entry point for the Oqoqo drift detection flow.
        
        Args:
            branch: The feature branch to check
            
        Returns:
            Dict with:
            - has_changes: bool
            - comparison: BranchComparison details
            - branch_file_content: The file content from the branch (if changed)
        """
        try:
            comparison = self.compare_branches(branch)
            
            result = {
                "has_changes": comparison.monitored_file_changed,
                "branch": branch,
                "base_branch": comparison.base_branch,
                "total_files_changed": len(comparison.files),
                "monitored_file": self.monitored_file,
                "ahead_by": comparison.ahead_by,
                "behind_by": comparison.behind_by,
                "status": comparison.status,
            }
            
            if comparison.monitored_file_changed:
                # Fetch the full file content from the branch
                try:
                    branch_content = self.get_monitored_file_from_branch(branch)
                    result["branch_file_content"] = branch_content
                    result["patch"] = comparison.monitored_file_patch
                except GitHubAPIError as e:
                    logger.error(f"[GITHUB PR SERVICE] Failed to fetch file content: {e}")
                    result["branch_file_content"] = None
                    result["error"] = str(e)
            
            return result
            
        except GitHubAPIError as e:
            logger.error(f"[GITHUB PR SERVICE] Error checking branch: {e}")
            return {
                "has_changes": False,
                "error": str(e),
                "branch": branch,
                "monitored_file": self.monitored_file,
            }
    
    def list_branches(self) -> List[str]:
        """List all branches in the repository."""
        endpoint = f"/repos/{self.owner}/{self.repo}/branches"
        data = self._make_request(endpoint)
        return [branch["name"] for branch in data]

    def fetch_pr_details(self, pr_number: int) -> Dict[str, Any]:
        """
        Fetch full PR details from GitHub API.

        Args:
            pr_number: PR number to fetch

        Returns:
            Dict with normalized PR metadata:
            {
                "number": int,
                "title": str,
                "body": str,
                "state": "open" | "closed",
                "merged": bool,
                "author": str,
                "base_branch": str,
                "head_branch": str,
                "url": str,
                "created_at": ISO8601,
                "updated_at": ISO8601,
                "merged_at": ISO8601 | None,
                "files_changed": int,
                "additions": int,
                "deletions": int,
            }
        """
        logger.info(f"[GITHUB PR SERVICE] Fetching PR #{pr_number}")

        # GET /repos/{owner}/{repo}/pulls/{pr_number}
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
        data = self._make_request(endpoint)

        # Normalize PR data
        pr_details = {
            "number": data.get("number"),
            "title": data.get("title", ""),
            "body": data.get("body", ""),
            "state": data.get("state", "open"),
            "merged": data.get("merged", False),
            "author": data.get("user", {}).get("login", "unknown"),
            "base_branch": data.get("base", {}).get("ref", ""),
            "head_branch": data.get("head", {}).get("ref", ""),
            "url": data.get("html_url", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "merged_at": data.get("merged_at"),
            "files_changed": data.get("changed_files", 0),
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
        }

        logger.info(f"[GITHUB PR SERVICE] Fetched PR #{pr_number}: {pr_details['title']}")

        return pr_details

    def fetch_pr_diff_summary(self, pr_number: int) -> Dict[str, Any]:
        """
        Fetch diff summary (changed files) for a PR.

        Args:
            pr_number: PR number to fetch diff for

        Returns:
            Dict with:
            {
                "files": [
                    {
                        "filename": str,
                        "status": "added" | "modified" | "removed" | "renamed",
                        "additions": int,
                        "deletions": int,
                        "changes": int,
                    }
                ],
                "total_files": int,
                "total_additions": int,
                "total_deletions": int,
                "summary": str,  # Human-readable summary
            }
        """
        logger.info(f"[GITHUB PR SERVICE] Fetching diff for PR #{pr_number}")

        # GET /repos/{owner}/{repo}/pulls/{pr_number}/files
        endpoint = f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files"
        files_data = self._make_request(endpoint)

        # Normalize file changes
        files = []
        total_additions = 0
        total_deletions = 0

        for file_data in files_data:
            file_info = {
                "filename": file_data.get("filename", ""),
                "status": file_data.get("status", "unknown"),
                "additions": file_data.get("additions", 0),
                "deletions": file_data.get("deletions", 0),
                "changes": file_data.get("changes", 0),
            }
            files.append(file_info)
            total_additions += file_info["additions"]
            total_deletions += file_info["deletions"]

        # Generate human-readable summary
        summary_parts = []
        if files:
            summary_parts.append(f"{len(files)} file{'s' if len(files) != 1 else ''} changed")
            if total_additions > 0:
                summary_parts.append(f"{total_additions} addition{'s' if total_additions != 1 else ''}")
            if total_deletions > 0:
                summary_parts.append(f"{total_deletions} deletion{'s' if total_deletions != 1 else ''}")
            summary = ", ".join(summary_parts)
        else:
            summary = "No files changed"

        diff_summary = {
            "files": files,
            "total_files": len(files),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "summary": summary,
        }

        logger.info(f"[GITHUB PR SERVICE] Diff summary: {summary}")

        return diff_summary

    def list_commits(
        self,
        branch: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        per_page: int = 30,
        include_files: bool = True,
        author: Optional[str] = None,
        path: Optional[str] = None,
        message_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List commits on a branch with optional filters.

        Args:
            branch: Branch/ref name (defaults to configured base branch)
            since: ISO timestamp string; only commits after this will be returned
            until: ISO timestamp string; only commits before this will be returned
            per_page: Max commits to return (GitHub API limit 100)
            include_files: Fetch per-commit file metadata
            author: Filter commits by author username/email
            path: Restrict commits to a specific file path
            message_query: Filter commit messages containing this substring (case-insensitive)
        """
        per_page = max(1, min(per_page, 100))
        params: Dict[str, Any] = {"per_page": per_page}

        branch_or_base = branch or self.base_branch
        if branch_or_base:
            params["sha"] = branch_or_base
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if author:
            params["author"] = author
        if path:
            params["path"] = path

        endpoint = self._repo_endpoint("/commits")
        commits_data = self._make_request(endpoint, params=params)
        commits: List[Dict[str, Any]] = []

        for commit_data in commits_data:
            sha = commit_data.get("sha")
            commit_info = commit_data.get("commit", {}) or {}
            author_info = commit_info.get("author") or {}
            committer_info = commit_info.get("committer") or {}
            author_login = commit_data.get("author", {}) or {}

            message = commit_info.get("message", "") or ""
            if message_query and message_query.lower() not in message.lower():
                continue

            files: List[Dict[str, Any]] = []
            if include_files and sha:
                detail = self._make_request(self._repo_endpoint(f"/commits/{sha}"))
                files = detail.get("files", []) or []

            commits.append(
                {
                    "sha": sha,
                    "short_sha": sha[:7] if sha else "",
                    "message": message,
                    "author": author_info.get("name") or author_login.get("login"),
                    "author_email": author_info.get("email"),
                    "author_login": author_login.get("login"),
                    "date": author_info.get("date") or committer_info.get("date"),
                    "url": commit_data.get("html_url", ""),
                    "files": files,
                    "parents": commit_data.get("parents", []),
                }
            )

        logger.info("[GITHUB PR SERVICE] Retrieved %s commits", len(commits))
        return commits

    def list_review_comments(
        self,
        pr_number: int,
        *,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        comments: List[Dict[str, Any]] = []
        page = 1
        while True:
            params = {"per_page": max(1, min(per_page, 100)), "page": page}
            endpoint = self._repo_endpoint(f"/pulls/{pr_number}/comments")
            data = self._make_request(endpoint, params=params)
            if not isinstance(data, list):
                break
            comments.extend(data)
            if len(data) < per_page:
                break
            page += 1
        normalized: List[Dict[str, Any]] = []
        for comment in comments:
            normalized.append(
                {
                    "id": comment.get("id"),
                    "body": comment.get("body"),
                    "user": (comment.get("user") or {}).get("login"),
                    "created_at": comment.get("created_at"),
                    "updated_at": comment.get("updated_at"),
                    "html_url": comment.get("html_url"),
                    "path": comment.get("path"),
                    "position": comment.get("position"),
                }
            )
        return normalized

    def list_issue_comments(
        self,
        issue_number: int,
        *,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        comments: List[Dict[str, Any]] = []
        page = 1
        while True:
            params = {"per_page": max(1, min(per_page, 100)), "page": page}
            endpoint = self._repo_endpoint(f"/issues/{issue_number}/comments")
            data = self._make_request(endpoint, params=params)
            if not isinstance(data, list):
                break
            comments.extend(data)
            if len(data) < per_page:
                break
            page += 1
        normalized: List[Dict[str, Any]] = []
        for comment in comments:
            normalized.append(
                {
                    "id": comment.get("id"),
                    "body": comment.get("body"),
                    "user": (comment.get("user") or {}).get("login"),
                    "created_at": comment.get("created_at"),
                    "updated_at": comment.get("updated_at"),
                    "html_url": comment.get("html_url"),
                }
            )
        return normalized

    def search_commits_by_message(
        self,
        query: str,
        branch: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search commit messages using GitHub's search API (preview header required).
        """
        if not query:
            return []

        limit = max(1, min(limit, 100))
        search_terms = [f"repo:{self.owner}/{self.repo}", query]
        if branch:
            search_terms.append(f"branch:{branch}")

        params = {
            "q": "+".join(search_terms),
            "per_page": limit,
            "sort": "committer-date",
            "order": "desc",
        }

        headers = {"Accept": "application/vnd.github.cloak-preview"}
        data = self._make_request("/search/commits", params=params, headers=headers)
        items = data.get("items", [])
        commits: List[Dict[str, Any]] = []
        for item in items:
            commit_info = item.get("commit", {}) or {}
            author_info = commit_info.get("author") or {}
            commits.append(
                {
                    "sha": item.get("sha"),
                    "short_sha": (item.get("sha") or "")[:7],
                    "message": commit_info.get("message"),
                    "author": author_info.get("name"),
                    "author_email": author_info.get("email"),
                    "date": author_info.get("date"),
                    "url": item.get("html_url"),
                    "score": item.get("score"),
                }
            )

        return commits

    def list_prs(
        self,
        state: str = "all",
        base_branch: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List PRs from GitHub API with optional filtering.

        Args:
            state: "open", "closed", or "all"
            base_branch: Filter by base branch (e.g., "main")
            limit: Max PRs to return (max 100)

        Returns:
            List of PR metadata (same schema as fetch_pr_details, but less detailed)
        """
        logger.info(f"[GITHUB PR SERVICE] Listing PRs (state={state}, base={base_branch}, limit={limit})")

        # Validate state parameter
        if state not in ["open", "closed", "all"]:
            state = "all"

        # Clamp limit
        limit = max(1, min(limit, 100))

        # GET /repos/{owner}/{repo}/pulls?state={state}&per_page={limit}
        params = []
        params.append(f"state={state}")
        params.append(f"per_page={limit}")
        params.append("sort=updated")
        params.append("direction=desc")

        if base_branch:
            params.append(f"base={base_branch}")

        endpoint = f"/repos/{self.owner}/{self.repo}/pulls?{'&'.join(params)}"
        prs_data = self._make_request(endpoint)

        # Normalize PR list
        prs = []
        for pr_data in prs_data:
            pr_info = {
                "number": pr_data.get("number"),
                "title": pr_data.get("title", ""),
                "state": pr_data.get("state", "open"),
                "author": pr_data.get("user", {}).get("login", "unknown"),
                "base_branch": pr_data.get("base", {}).get("ref", ""),
                "head_branch": pr_data.get("head", {}).get("ref", ""),
                "url": pr_data.get("html_url", ""),
                "created_at": pr_data.get("created_at", ""),
                "updated_at": pr_data.get("updated_at", ""),
                "merged_at": pr_data.get("merged_at"),
            }
            prs.append(pr_info)

        logger.info(f"[GITHUB PR SERVICE] Found {len(prs)} PRs")

        return prs

    def list_branch_pull_requests(
        self,
        branch: str,
        state: str = "open",
        limit: int = 10,
        match_head: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List pull requests associated with a branch.

        Args:
            branch: Branch name to filter by.
            state: PR state ("open", "closed", "all")
            limit: Max PRs to return.
            match_head: When True, match branch as the head ref instead of base.
        """
        if not branch:
            return []

        if match_head:
            params = {
                "state": state,
                "per_page": max(1, min(limit, 100)),
                "head": f"{self.owner}:{branch}",
            }
            endpoint = self._repo_endpoint("/pulls")
            prs_data = self._make_request(endpoint, params=params)
        else:
            prs_data = self.list_prs(state=state, base_branch=branch, limit=limit)
            return prs_data

        prs = []
        for pr_data in prs_data:
            prs.append(
                {
                    "number": pr_data.get("number"),
                    "title": pr_data.get("title", ""),
                    "state": pr_data.get("state", "open"),
                    "author": pr_data.get("user", {}).get("login", "unknown"),
                    "base_branch": pr_data.get("base", {}).get("ref", ""),
                    "head_branch": pr_data.get("head", {}).get("ref", ""),
                    "url": pr_data.get("html_url", ""),
                    "created_at": pr_data.get("created_at", ""),
                    "updated_at": pr_data.get("updated_at", ""),
                    "merged_at": pr_data.get("merged_at"),
                }
            )
        return prs

    def get_commit(self, sha: str, include_files: bool = True) -> Dict[str, Any]:
        """Fetch detailed commit metadata."""
        if not sha:
            raise GitHubAPIError("Commit SHA is required")

        endpoint = self._repo_endpoint(f"/commits/{sha}")
        detail = self._make_request(endpoint)
        commit_info = detail.get("commit", {}) or {}
        author_info = commit_info.get("author") or {}
        committer_info = commit_info.get("committer") or {}

        result = {
            "sha": detail.get("sha"),
            "short_sha": (detail.get("sha") or "")[:7],
            "message": commit_info.get("message"),
            "author": author_info.get("name"),
            "author_email": author_info.get("email"),
            "committer": committer_info.get("name"),
            "date": author_info.get("date") or committer_info.get("date"),
            "url": detail.get("html_url"),
            "parents": detail.get("parents", []),
        }

        if include_files:
            result["files"] = detail.get("files", []) or []

        return result

    def list_file_history(
        self,
        path: str,
        branch: Optional[str] = None,
        limit: int = 10,
        author: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List recent commits that touched a specific file."""
        if not path:
            return []

        commits = self.list_commits(
            branch=branch,
            path=path,
            per_page=limit,
            include_files=False,
            author=author,
        )
        return commits

    def compare_refs(self, base_ref: str, head_ref: str) -> Dict[str, Any]:
        """Compare arbitrary refs (branches, tags, SHAs)."""
        if not base_ref or not head_ref:
            raise GitHubAPIError("Both base and head refs are required")

        endpoint = self._repo_endpoint(f"/compare/{base_ref}...{head_ref}")
        data = self._make_request(endpoint)

        files = []
        for file_data in data.get("files", []):
            files.append(
                {
                    "filename": file_data.get("filename"),
                    "status": file_data.get("status"),
                    "additions": file_data.get("additions", 0),
                    "deletions": file_data.get("deletions", 0),
                    "changes": file_data.get("changes", 0),
                    "patch": file_data.get("patch"),
                }
            )

        comparison = {
            "base_ref": base_ref,
            "head_ref": head_ref,
            "status": data.get("status"),
            "ahead_by": data.get("ahead_by", 0),
            "behind_by": data.get("behind_by", 0),
            "total_commits": data.get("total_commits", 0),
            "files": files,
            "commits": [
                {
                    "sha": commit.get("sha"),
                    "message": (commit.get("commit") or {}).get("message"),
                    "author": ((commit.get("commit") or {}).get("author") or {}).get("name"),
                    "date": ((commit.get("commit") or {}).get("author") or {}).get("date"),
                    "url": commit.get("html_url"),
                }
                for commit in data.get("commits", [])
            ],
        }

        return comparison

    def list_tags(self, per_page: int = 20, include_commit_dates: bool = True) -> List[Dict[str, Any]]:
        """List repository tags ordered from newest to oldest."""
        params = {"per_page": max(1, min(per_page, 100))}
        endpoint = self._repo_endpoint("/tags")
        tags_data = self._make_request(endpoint, params=params)

        tags: List[Dict[str, Any]] = []
        for tag in tags_data:
            commit_sha = (tag.get("commit") or {}).get("sha")
            commit_date = None
            if include_commit_dates and commit_sha:
                try:
                    commit_detail = self._make_request(self._repo_endpoint(f"/commits/{commit_sha}"))
                    commit_date = ((commit_detail.get("commit") or {}).get("author") or {}).get("date")
                except Exception as exc:
                    logger.warning(f"[GITHUB PR SERVICE] Failed to fetch commit for tag {tag.get('name')}: {exc}")

            tags.append(
                {
                    "name": tag.get("name"),
                    "commit_sha": commit_sha,
                    "zipball_url": tag.get("zipball_url"),
                    "tarball_url": tag.get("tarball_url"),
                    "commit_date": commit_date,
                }
            )

        return tags

    def get_latest_tag(self) -> Optional[Dict[str, Any]]:
        """Return the most recent tag (if any)."""
        tags = self.list_tags(per_page=1)
        return tags[0] if tags else None

    def list_issues(
        self,
        state: str = "all",
        labels: Optional[List[str]] = None,
        since: Optional[str] = None,
        limit: int = 30,
        include_pull_requests: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List issues (optionally filtered by labels/state) for the configured repository.

        Args:
            state: "open", "closed", or "all"
            labels: List of label names to filter on
            since: ISO timestamp; only issues updated after this are returned
            limit: Max items per page (GitHub caps at 100)
            include_pull_requests: When False, PRs returned by the issues API are skipped
        """
        if state not in {"open", "closed", "all"}:
            state = "all"
        limit = max(1, min(limit, 100))

        query_params: Dict[str, Any] = {
            "state": state,
            "per_page": limit,
            "sort": "updated",
            "direction": "desc",
        }
        if since:
            query_params["since"] = since
        if labels:
            query_params["labels"] = ",".join(labels)

        endpoint = f"/repos/{self.owner}/{self.repo}/issues"
        issues_data = self._make_request(endpoint, params=query_params)

        issues: List[Dict[str, Any]] = []
        for issue_data in issues_data:
            # Issues API also returns PRs; optionally skip them
            if not include_pull_requests and issue_data.get("pull_request"):
                continue

            issues.append(
                {
                    "number": issue_data.get("number"),
                    "title": issue_data.get("title", ""),
                    "body": issue_data.get("body", "") or "",
                    "state": issue_data.get("state", "open"),
                    "labels": issue_data.get("labels", []) or [],
                    "comments": issue_data.get("comments", 0),
                    "author": issue_data.get("user", {}).get("login", "unknown"),
                    "created_at": issue_data.get("created_at"),
                    "updated_at": issue_data.get("updated_at"),
                    "url": issue_data.get("html_url"),
                    "reactions": issue_data.get("reactions", {}) or {},
                }
            )

        logger.info(f"[GITHUB PR SERVICE] Found {len(issues)} issues (state={state})")
        return issues


class GitHubAPIError(Exception):
    """Exception raised for GitHub API errors."""
    pass


# Singleton instance
_github_service_instance: Optional[GitHubPRService] = None


def get_github_pr_service() -> GitHubPRService:
    """Get or create the singleton GitHub PR service instance."""
    global _github_service_instance
    if _github_service_instance is None:
        _github_service_instance = GitHubPRService()
    return _github_service_instance

