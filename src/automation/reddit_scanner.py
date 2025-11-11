"""
Reddit scanning automation powered by Playwright.

This module keeps Reddit-specific scraping logic separate from higher-level
agents so planners can re-use it for multiple workflows (summaries, reports,
trend analysis, etc.).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


class RedditScanner:
    """High-level helper that scrapes subreddit feeds and comment threads."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        reddit_cfg = config.get("reddit", {}) or {}

        self.headless_default = reddit_cfg.get("headless", True)
        self.default_sort = reddit_cfg.get("default_sort", "hot")
        self.scroll_pause_ms = reddit_cfg.get("scroll_pause_ms", 1200)
        self.max_scroll_iterations = reddit_cfg.get("max_scroll_iterations", 10)
        self.comment_threads_limit = reddit_cfg.get("comment_threads_limit")

        viewport_cfg = reddit_cfg.get("viewport") or {"width": 1280, "height": 900}
        self.viewport = {
            "width": viewport_cfg.get("width", 1280),
            "height": viewport_cfg.get("height", 900)
        }

        self.user_agent = reddit_cfg.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        self.base_url = reddit_cfg.get("base_url", "https://www.reddit.com")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def scan_subreddit(
        self,
        subreddit: str,
        *,
        sort: Optional[str] = None,
        limit_posts: int = 10,
        include_comments: bool = True,
        comments_limit: int = 5,
        comment_threads_limit: Optional[int] = None,
        headless: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Crawl a subreddit feed, returning structured post + comment data.

        Args:
            subreddit: Target subreddit ("startups", "SideProject", etc.)
            sort: Reddit sort key (hot, new, top, rising)
            limit_posts: Max number of posts to return
            include_comments: When True, fetch top-level comments for each post
            comments_limit: Max comments per post
            comment_threads_limit: How many posts should fetch comments (default = limit_posts or config)
            headless: Override headless mode
        """
        normalized_subreddit = subreddit.replace("/r/", "").replace("r/", "").strip()
        if not normalized_subreddit:
            raise ValueError("Subreddit name cannot be empty.")

        sort = (sort or self.default_sort).strip("/") or self.default_sort
        headless = self.headless_default if headless is None else headless
        target_url = f"{self.base_url}/r/{normalized_subreddit}/{sort}"

        logger.info(
            "[REDDIT] Scanning subreddit=%s sort=%s posts=%s comments=%s headless=%s",
            normalized_subreddit, sort, limit_posts, include_comments, headless
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(
                    viewport=self.viewport,
                    user_agent=self.user_agent,
                    locale="en-US"
                )

                page = context.new_page()
                self._goto(page, target_url)
                self._dismiss_popups(page)
                page.wait_for_selector('article[data-testid="post-container"]', timeout=15000)

                self._auto_scroll(page, target_post_count=limit_posts)
                raw_posts = self._extract_posts(page)

                posts = self._postprocess_posts(raw_posts)[:limit_posts]

                if include_comments and posts:
                    threads_cap = comment_threads_limit or self.comment_threads_limit or limit_posts
                    threads_cap = max(1, min(threads_cap, len(posts)))
                    for post in posts[:threads_cap]:
                        comments = self._collect_comments(context, post["url"], comments_limit)
                        post["top_comments"] = comments

                result = {
                    "subreddit": normalized_subreddit,
                    "sort": sort,
                    "url": target_url,
                    "retrieved_at": datetime.utcnow().isoformat() + "Z",
                    "post_count": len(posts),
                    "posts": posts
                }

                context.close()
                browser.close()
                return result

        except Exception as exc:
            logger.error("[REDDIT] Subreddit scan failed: %s", exc)
            return {
                "error": True,
                "error_type": "RedditScanError",
                "error_message": str(exc),
                "retry_possible": True
            }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _goto(self, page, url: str):
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
        except PlaywrightTimeout:
            logger.warning("[REDDIT] Navigation timeout for %s", url)
        finally:
            page.wait_for_timeout(1500)

    def _dismiss_popups(self, page):
        """Close cookie / sign-in modals when they appear."""
        candidates = [
            'button:has-text("Accept all")',
            'button:has-text("Accept All")',
            'button[data-test="accept-all"]',
            'button:has-text("Continue")',
            'button:has-text("Got it")'
        ]
        for selector in candidates:
            try:
                page.locator(selector).first.click(timeout=1500)
                logger.info("[REDDIT] Dismissed consent dialog via %s", selector)
                break
            except Exception:
                continue

    def _auto_scroll(self, page, target_post_count: int):
        """Scroll feed until we collect enough posts or reach limits."""
        scrolls = 0
        while scrolls < self.max_scroll_iterations:
            current_count = page.evaluate(
                '() => document.querySelectorAll("article[data-testid=\'post-container\']").length'
            )
            if current_count >= target_post_count:
                break
            page.mouse.wheel(0, 2200)
            page.wait_for_timeout(self.scroll_pause_ms)
            scrolls += 1

    def _extract_posts(self, page) -> List[Dict[str, Any]]:
        """Return raw post objects directly from the DOM."""
        script = """
        () => {
            const posts = [];
            const containers = document.querySelectorAll('article[data-testid="post-container"]');

            containers.forEach((article, idx) => {
                const titleEl = article.querySelector('h3');
                const bodyLink = article.querySelector('a[data-click-id="body"]');
                const commentsLink = article.querySelector('a[data-click-id="comments"]');
                const authorEl = article.querySelector('a[data-click-id="user"]');
                const voteEl = article.querySelector('[id*="vote-arrows"] + div, div[data-test-id="score"]');
                const commentCountEl = commentsLink ? commentsLink.querySelector('span') : null;
                const timestampEl = article.querySelector('a[data-click-id="timestamp"]');
                const flairEl = article.querySelector('[data-testid*="post-flair-badge"], span[class*="flair"]');
                const snippetEl = article.querySelector('[data-click-id="text"] p');
                const imageEl = article.querySelector('img[alt="Post image"], figure img');

                posts.push({
                    rank: idx + 1,
                    title: titleEl ? titleEl.innerText : "",
                    url: bodyLink ? bodyLink.href : (commentsLink ? commentsLink.href : ""),
                    commentsUrl: commentsLink ? commentsLink.href : "",
                    author: authorEl ? authorEl.innerText : "",
                    voteText: voteEl ? voteEl.innerText : "",
                    commentText: commentCountEl ? commentCountEl.innerText : "",
                    timestamp: timestampEl ? timestampEl.innerText : "",
                    flair: flairEl ? flairEl.innerText : "",
                    snippet: snippetEl ? snippetEl.innerText : "",
                    image: imageEl ? imageEl.src : ""
                });
            });

            return posts;
        }
        """
        return page.evaluate(script)

    def _postprocess_posts(self, raw_posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed: List[Dict[str, Any]] = []
        for post in raw_posts:
            if not post.get("title"):
                continue

            permalink = post.get("commentsUrl") or post.get("url")
            full_url = permalink if permalink.startswith("http") else urljoin(self.base_url, permalink or "")

            processed.append({
                "rank": post.get("rank"),
                "title": post.get("title", "").strip(),
                "url": full_url,
                "author": post.get("author") or "unknown",
                "flair": post.get("flair") or None,
                "snippet": post.get("snippet") or None,
                "preview_image": post.get("image") or None,
                "posted_ago": post.get("timestamp") or None,
                "upvotes": self._parse_count(post.get("voteText")),
                "comments_count": self._parse_count(post.get("commentText")),
                "vote_text": post.get("voteText") or None,
                "comment_text": post.get("commentText") or None,
            })
        return processed

    def _collect_comments(self, context, post_url: str, comments_limit: int) -> List[Dict[str, Any]]:
        """Open a post and collect top-level comments."""
        comments_page = context.new_page()
        try:
            self._goto(comments_page, post_url)
            self._dismiss_popups(comments_page)
            comments_page.wait_for_timeout(1200)

            script = """
            (limit) => {
                const comments = [];
                const nodes = document.querySelectorAll('div[data-test-id="comment"]');
                for (const node of nodes) {
                    if (comments.length >= limit) break;
                    const authorEl = node.querySelector('a[data-click-id="user"]');
                    const bodyEl = node.querySelector('[data-testid="comment"] p, div[data-testid="comment"]');
                    const scoreEl = node.querySelector('[id*="vote-arrows"] + div');
                    const timestampEl = node.querySelector('a[data-click-id="timestamp"]');

                    comments.push({
                        author: authorEl ? authorEl.innerText : "anonymous",
                        body: bodyEl ? bodyEl.innerText : node.innerText,
                        scoreText: scoreEl ? scoreEl.innerText : "",
                        timestamp: timestampEl ? timestampEl.innerText : ""
                    });
                }
                return comments;
            }
            """
            raw_comments = comments_page.evaluate(script, max(1, comments_limit))

            cleaned: List[Dict[str, Any]] = []
            for comment in raw_comments:
                text = (comment.get("body") or "").strip()
                if not text:
                    continue
                cleaned.append({
                    "author": comment.get("author") or "anonymous",
                    "body": text,
                    "posted_ago": comment.get("timestamp") or None,
                    "score": self._parse_count(comment.get("scoreText")),
                    "score_text": comment.get("scoreText") or None
                })
            return cleaned
        except Exception as exc:
            logger.warning("[REDDIT] Failed to gather comments for %s: %s", post_url, exc)
            return []
        finally:
            comments_page.close()

    def _parse_count(self, text: Optional[str]) -> Optional[int]:
        """Convert strings like '1.2k' or '3 comments' to integers."""
        if not text:
            return None
        cleaned = text.strip().lower()
        if "score hidden" in cleaned or "vote" in cleaned and any(ch.isalpha() for ch in cleaned.replace("votes", "")):
            cleaned = cleaned.replace("votes", "").strip()
        for token in ["votes", "vote", "comments", "comment", "•", "upvotes"]:
            cleaned = cleaned.replace(token, "")
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        multiplier = 1
        if cleaned.endswith("k"):
            multiplier = 1_000
            cleaned = cleaned[:-1]
        elif cleaned.endswith("m"):
            multiplier = 1_000_000
            cleaned = cleaned[:-1]
        try:
            value = float(cleaned)
            return int(value * multiplier)
        except ValueError:
            return None
