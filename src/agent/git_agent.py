"""
Git Agent - Query and analyze GitHub PR events.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_github_service():
    """Helper to initialize GitHubPRService with current config."""
    from ..utils import load_config
    from src.services.github_pr_service import GitHubPRService

    config = load_config()
    return GitHubPRService(config)


@tool
def list_recent_prs(
    limit: int = 10,
    state: str = "all",
    branch: Optional[str] = None,
    use_live_api: bool = True
) -> Dict[str, Any]:
    """
    List recent PR events from webhook storage OR live GitHub API.

    Args:
        limit: Maximum number of PRs to return (default 10, max 50)
        state: "open", "closed", or "all" (only for live API, default "all")
        branch: Filter by base branch (e.g., "main")
        use_live_api: If True, fetch from GitHub API; if False, use webhook cache (default True)

    Returns:
        Dictionary with PR list and metadata
    """
    limit = max(1, min(limit, 50))

    try:
        from ..utils import load_config
        config = load_config()

        if use_live_api:
            # Fetch from GitHub API
            try:
                from src.services.github_pr_service import GitHubPRService
                service = GitHubPRService(config)
                prs = service.list_prs(state=state, base_branch=branch, limit=limit)
                source = "github_api"

                logger.info(f"[GIT AGENT] Fetched {len(prs)} PRs from GitHub API")

            except Exception as api_exc:
                logger.warning(f"[GIT AGENT] GitHub API failed, falling back to webhook cache: {api_exc}")
                # Fall back to webhook cache
                from src.services.github_webhook_service import GitHubWebhookService
                webhook_service = GitHubWebhookService(config)
                prs = webhook_service.get_recent_prs(limit=limit)
                source = "webhook_cache"
        else:
            # Use webhook cache
            from src.services.github_webhook_service import GitHubWebhookService
            webhook_service = GitHubWebhookService(config)
            prs = webhook_service.get_recent_prs(limit=limit)
            source = "webhook_cache"

            logger.info(f"[GIT AGENT] Fetched {len(prs)} PRs from webhook cache")

        if not prs:
            return {
                "count": 0,
                "source": source,
                "prs": [],
                "message": "No PRs found. Make sure GitHub webhook is configured or repository has PRs.",
            }

        return {
            "count": len(prs),
            "source": source,
            "prs": prs,
        }

    except Exception as exc:
        logger.exception("Error listing recent PRs")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
            "retry_possible": True,
        }


@tool
def get_pr_details(
    pr_number: int,
    include_diff: bool = True
) -> Dict[str, Any]:
    """
    Get detailed information about a specific PR from GitHub API.

    Args:
        pr_number: PR number to lookup
        include_diff: Include diff/file change summary (default True)

    Returns:
        Dictionary with PR details and optional diff summary
    """
    if not pr_number or pr_number <= 0:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "PR number must be a positive integer.",
            "retry_possible": False,
        }

    try:
        from src.services.github_pr_service import GitHubPRService
        from ..utils import load_config

        config = load_config()
        service = GitHubPRService(config)

        # Fetch PR details from GitHub API
        try:
            pr = service.fetch_pr_details(pr_number)
            result = {"pr": pr}

            # Optionally fetch diff summary
            if include_diff:
                try:
                    diff_summary = service.fetch_pr_diff_summary(pr_number)
                    result["diff_summary"] = diff_summary
                except Exception as diff_exc:
                    logger.warning(f"[GIT AGENT] Failed to fetch diff for PR #{pr_number}: {diff_exc}")
                    result["diff_summary"] = {
                        "error": "Failed to fetch diff summary",
                        "files": [],
                        "total_files": 0,
                    }

            logger.info(f"[GIT AGENT] Fetched details for PR #{pr_number} from GitHub API")

            return result

        except Exception as api_exc:
            # Fall back to webhook cache if API fails
            logger.warning(f"[GIT AGENT] GitHub API failed for PR #{pr_number}, trying webhook cache: {api_exc}")

            from src.services.github_webhook_service import GitHubWebhookService
            webhook_service = GitHubWebhookService(config)
            pr = webhook_service.get_pr_by_number(pr_number)

            if not pr:
                return {
                    "error": True,
                    "error_type": "NotFound",
                    "error_message": f"PR #{pr_number} not found in GitHub API or webhook history.",
                    "retry_possible": False,
                }

            logger.info(f"[GIT AGENT] Fetched PR #{pr_number} from webhook cache (fallback)")

            return {
                "pr": pr,
                "source": "webhook_cache",
                "diff_summary": None,  # Not available from webhook cache
            }

    except Exception as exc:
        logger.exception(f"Error getting PR #{pr_number}")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
            "retry_possible": True,
        }


@tool
def get_repo_overview() -> Dict[str, Any]:
    """
    Fetch repository metadata (name, default branch, description, stats).
    """
    try:
        service = _get_github_service()
        repo = service.get_repo_info()
        return {"repo": repo}
    except Exception as exc:
        logger.exception("Error fetching repo info")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def list_repository_branches(
    limit: int = 50,
    names_only: bool = False
) -> Dict[str, Any]:
    """
    List repository branches with optional metadata.
    """
    try:
        service = _get_github_service()
        branches = service.list_branches(names_only=names_only, limit=limit)
        default_branch = service.get_default_branch()
        return {
            "count": len(branches),
            "branches": branches,
            "default_branch": default_branch,
        }
    except Exception as exc:
        logger.exception("Error listing branches")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def list_branch_commits(
    branch: Optional[str] = None,
    limit: int = 10,
    since: Optional[str] = None,
    until: Optional[str] = None,
    author: Optional[str] = None,
    path: Optional[str] = None,
    message_query: Optional[str] = None,
    include_files: bool = False,
) -> Dict[str, Any]:
    """
    List commits on a branch with optional filters.
    """
    try:
        service = _get_github_service()
        commits = service.list_commits(
            branch=branch,
            since=since,
            until=until,
            per_page=max(1, min(limit, 100)),
            include_files=include_files,
            author=author,
            path=path,
            message_query=message_query,
        )
        return {
            "count": len(commits),
            "branch": branch or service.base_branch,
            "commits": commits,
        }
    except Exception as exc:
        logger.exception("Error listing commits")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def search_branch_commits(
    keyword: str,
    branch: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Search commit messages for a keyword.
    """
    if not keyword:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Keyword is required for commit search.",
        }

    try:
        service = _get_github_service()
        commits = service.search_commits_by_message(keyword, branch=branch, limit=limit)
        return {
            "count": len(commits),
            "keyword": keyword,
            "branch": branch,
            "commits": commits,
        }
    except Exception as exc:
        logger.exception("Error searching commits")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def get_commit_details(
    sha: str,
    include_files: bool = True
) -> Dict[str, Any]:
    """
    Fetch metadata for a specific commit.
    """
    if not sha:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Commit SHA is required.",
        }

    try:
        service = _get_github_service()
        commit = service.get_commit(sha, include_files=include_files)
        return {"commit": commit}
    except Exception as exc:
        logger.exception("Error fetching commit details")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def list_file_history(
    path: str,
    branch: Optional[str] = None,
    limit: int = 10,
    author: Optional[str] = None
) -> Dict[str, Any]:
    """
    List recent commits that touched a specific file.
    """
    if not path:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "File path is required.",
        }

    try:
        service = _get_github_service()
        commits = service.list_file_history(path=path, branch=branch, limit=limit, author=author)
        return {
            "path": path,
            "branch": branch or service.base_branch,
            "commits": commits,
        }
    except Exception as exc:
        logger.exception("Error listing file history")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def compare_git_refs(
    base_ref: str,
    head_ref: str,
) -> Dict[str, Any]:
    """
    Compare two refs (branches/tags/SHAs) and return diff summary.
    """
    if not base_ref or not head_ref:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Both base_ref and head_ref are required.",
        }

    try:
        service = _get_github_service()
        comparison = service.compare_refs(base_ref, head_ref)
        return {"comparison": comparison}
    except Exception as exc:
        logger.exception("Error comparing refs")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def list_repository_tags(
    limit: int = 20
) -> Dict[str, Any]:
    """
    List repository tags (semantic versions/releases).
    """
    try:
        service = _get_github_service()
        tags = service.list_tags(per_page=limit)
        return {
            "count": len(tags),
            "tags": tags,
        }
    except Exception as exc:
        logger.exception("Error listing tags")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def get_latest_repo_tag() -> Dict[str, Any]:
    """
    Fetch the most recent tag (if available).
    """
    try:
        service = _get_github_service()
        tag = service.get_latest_tag()
        if not tag:
            return {
                "count": 0,
                "message": "Repository has no tags.",
            }
        return {
            "tag": tag,
        }
    except Exception as exc:
        logger.exception("Error fetching latest tag")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }


@tool
def list_branch_pull_requests(
    branch: str,
    state: str = "open",
    limit: int = 10,
    match_head: bool = False,
) -> Dict[str, Any]:
    """
    List pull requests associated with a branch.
    """
    if not branch:
        return {
            "error": True,
            "error_type": "InvalidInput",
            "error_message": "Branch name is required.",
        }

    try:
        service = _get_github_service()
        prs = service.list_branch_pull_requests(
            branch=branch,
            state=state,
            limit=limit,
            match_head=match_head,
        )
        return {
            "count": len(prs),
            "branch": branch,
            "state": state,
            "prs": prs,
        }
    except Exception as exc:
        logger.exception("Error listing branch PRs")
        return {
            "error": True,
            "error_type": "GitAgentError",
            "error_message": str(exc),
        }
GIT_AGENT_TOOLS = [
    list_recent_prs,
    get_pr_details,
    get_repo_overview,
    list_repository_branches,
    list_branch_commits,
    search_branch_commits,
    get_commit_details,
    list_file_history,
    compare_git_refs,
    list_repository_tags,
    get_latest_repo_tag,
    list_branch_pull_requests,
]

GIT_AGENT_HIERARCHY = """
Git Agent Hierarchy:
===================

LEVEL 1: PR Querying
└─ list_recent_prs(limit=10, state="all", branch=None, use_live_api=True)
   → List recent PRs from webhook cache OR live GitHub API

└─ get_pr_details(pr_number, include_diff=True)
   → Get full PR details + diff summary from GitHub API

LEVEL 2: Repository & Branch Metadata
└─ get_repo_overview()
   → Fetch repo name, description, default branch, stats

└─ list_repository_branches(limit=50, names_only=False)
   → List branches with head SHA and default flag

LEVEL 3: Commits & Files
└─ list_branch_commits(branch=None, limit=10, since=None, author=None, path=None, message_query=None)
└─ search_branch_commits(keyword, branch=None, limit=20)
└─ get_commit_details(sha, include_files=True)
└─ list_file_history(path, branch=None, limit=10)

LEVEL 4: Refs, Tags, PRs
└─ compare_git_refs(base_ref, head_ref)
└─ list_repository_tags(limit=20)
└─ get_latest_repo_tag()
└─ list_branch_pull_requests(branch, state="open", limit=10, match_head=False)
"""


class GitAgent:
    """
    Orchestrates GitHub PR querying operations.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in GIT_AGENT_TOOLS}
        logger.info(f"[GIT AGENT] Initialized with {len(self.tools)} tools")

    def get_tools(self) -> List:
        return GIT_AGENT_TOOLS

    def get_hierarchy(self) -> str:
        return GIT_AGENT_HIERARCHY

    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Git agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys()),
            }

        tool = self.tools[tool_name]
        try:
            return tool.invoke(inputs)
        except Exception as exc:
            logger.exception("Git agent execution error")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(exc),
                "retry_possible": False,
            }
