"""
Screen time usage collector for macOS.

Queries the local Screen Time SQLite database to extract usage statistics.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class ScreenTimeCollector:
    """Collects screen time usage data from macOS Screen Time database."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize collector.

        Args:
            db_path: Path to Screen Time database (auto-detects if None)
        """
        if db_path is None:
            # Default macOS Screen Time database location
            home = Path.home()
            db_path = home / "Library" / "Application Support" / "Knowledge" / "knowledgeC.db"

        self.db_path = Path(db_path)

        if not self.db_path.exists():
            logger.warning(f"Screen Time database not found at {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    def collect_weekly_usage(self, weeks_back: int = 1) -> Dict[str, Any]:
        """
        Collect screen time usage for the past N weeks.

        Args:
            weeks_back: Number of weeks to look back (default 1)

        Returns:
            Dictionary containing usage statistics
        """
        if not self.db_path.exists():
            return self._get_mock_data()

        try:
            conn = self._connect()
            cursor = conn.cursor()

            # Calculate date range
            now = datetime.now()
            end_date = now
            start_date = now - timedelta(weeks=weeks_back)

            # Convert to Core Data timestamps (seconds since 2001-01-01)
            reference_date = datetime(2001, 1, 1)
            start_timestamp = (start_date - reference_date).total_seconds()
            end_timestamp = (end_date - reference_date).total_seconds()

            # Query screen time events
            # The Knowledge database stores app usage in ZOBJECT table
            query = """
                SELECT
                    ZOBJECT.ZVALUESTRING as app_name,
                    SUM(ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) as duration
                FROM ZOBJECT
                WHERE ZOBJECT.ZSTREAMNAME = '/app/usage'
                    AND ZOBJECT.ZSTARTDATE >= ?
                    AND ZOBJECT.ZENDDATE <= ?
                    AND ZOBJECT.ZVALUESTRING IS NOT NULL
                GROUP BY ZOBJECT.ZVALUESTRING
                ORDER BY duration DESC
            """

            cursor.execute(query, (start_timestamp, end_timestamp))
            results = cursor.fetchall()

            # Process results
            apps = []
            total_seconds = 0

            for app_name, duration in results:
                if duration > 0:
                    apps.append({
                        "name": app_name,
                        "duration_seconds": int(duration),
                        "duration_formatted": self._format_duration(duration)
                    })
                    total_seconds += duration

            conn.close()

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "weeks": weeks_back
                },
                "total_duration_seconds": int(total_seconds),
                "total_duration_formatted": self._format_duration(total_seconds),
                "apps": apps[:20],  # Top 20 apps
                "app_count": len(apps)
            }

        except sqlite3.Error as e:
            logger.error(f"Failed to query screen time database: {e}")
            return self._get_mock_data()

    def collect_daily_usage(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Collect daily screen time usage breakdown.

        Args:
            days_back: Number of days to look back

        Returns:
            Dictionary containing daily usage statistics
        """
        if not self.db_path.exists():
            return self._get_mock_daily_data()

        try:
            conn = self._connect()
            cursor = conn.cursor()

            # Calculate date range
            now = datetime.now()
            end_date = now
            start_date = now - timedelta(days=days_back)

            # Convert to Core Data timestamps
            reference_date = datetime(2001, 1, 1)
            start_timestamp = (start_date - reference_date).total_seconds()
            end_timestamp = (end_date - reference_date).total_seconds()

            # Query daily usage
            query = """
                SELECT
                    DATE(ZOBJECT.ZSTARTDATE + 978307200, 'unixepoch', 'localtime') as day,
                    SUM(ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) as duration
                FROM ZOBJECT
                WHERE ZOBJECT.ZSTREAMNAME = '/app/usage'
                    AND ZOBJECT.ZSTARTDATE >= ?
                    AND ZOBJECT.ZENDDATE <= ?
                GROUP BY day
                ORDER BY day DESC
            """

            cursor.execute(query, (start_timestamp, end_timestamp))
            results = cursor.fetchall()

            # Process results
            daily_breakdown = []
            for day, duration in results:
                daily_breakdown.append({
                    "date": day,
                    "duration_seconds": int(duration),
                    "duration_formatted": self._format_duration(duration)
                })

            conn.close()

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": days_back
                },
                "daily_breakdown": daily_breakdown
            }

        except sqlite3.Error as e:
            logger.error(f"Failed to query screen time database: {e}")
            return self._get_mock_daily_data()

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def _get_mock_data(self) -> Dict[str, Any]:
        """Return mock data when database is unavailable."""
        logger.info("Returning mock screen time data (database not available)")

        now = datetime.now()
        return {
            "period": {
                "start": (now - timedelta(weeks=1)).isoformat(),
                "end": now.isoformat(),
                "weeks": 1
            },
            "total_duration_seconds": 82800,  # ~23 hours
            "total_duration_formatted": "23h 0m",
            "apps": [
                {"name": "Safari", "duration_seconds": 18000, "duration_formatted": "5h 0m"},
                {"name": "VS Code", "duration_seconds": 14400, "duration_formatted": "4h 0m"},
                {"name": "Terminal", "duration_seconds": 10800, "duration_formatted": "3h 0m"},
                {"name": "Slack", "duration_seconds": 7200, "duration_formatted": "2h 0m"},
                {"name": "Chrome", "duration_seconds": 5400, "duration_formatted": "1h 30m"}
            ],
            "app_count": 5,
            "mock_data": True
        }

    def _get_mock_daily_data(self) -> Dict[str, Any]:
        """Return mock daily data when database is unavailable."""
        logger.info("Returning mock daily screen time data (database not available)")

        now = datetime.now()
        daily_breakdown = []

        for i in range(7):
            date = now - timedelta(days=i)
            daily_breakdown.append({
                "date": date.strftime("%Y-%m-%d"),
                "duration_seconds": 10800 + (i * 600),  # 3-4 hours per day
                "duration_formatted": self._format_duration(10800 + (i * 600))
            })

        return {
            "period": {
                "start": (now - timedelta(days=7)).isoformat(),
                "end": now.isoformat(),
                "days": 7
            },
            "daily_breakdown": daily_breakdown,
            "mock_data": True
        }

    def collect_category_usage(self) -> Dict[str, Any]:
        """
        Collect usage by category (productivity, entertainment, etc.).

        Note: This requires categorization logic not present in the raw database.
        Returns a simplified categorization based on app names.
        """
        weekly_data = self.collect_weekly_usage()

        # Simple categorization heuristics
        categories = {
            "productivity": ["VS Code", "Terminal", "Xcode", "PyCharm", "IntelliJ"],
            "communication": ["Slack", "Mail", "Messages", "Zoom", "Teams"],
            "browsers": ["Safari", "Chrome", "Firefox", "Edge"],
            "entertainment": ["Music", "Spotify", "Netflix", "YouTube"]
        }

        categorized = {
            "productivity": 0,
            "communication": 0,
            "browsers": 0,
            "entertainment": 0,
            "other": 0
        }

        for app in weekly_data.get("apps", []):
            categorized_flag = False

            for category, keywords in categories.items():
                if any(keyword.lower() in app["name"].lower() for keyword in keywords):
                    categorized[category] += app["duration_seconds"]
                    categorized_flag = True
                    break

            if not categorized_flag:
                categorized["other"] += app["duration_seconds"]

        return {
            "period": weekly_data["period"],
            "categories": {
                cat: {
                    "duration_seconds": duration,
                    "duration_formatted": self._format_duration(duration),
                    "percentage": round((duration / weekly_data["total_duration_seconds"]) * 100, 1)
                        if weekly_data["total_duration_seconds"] > 0 else 0
                }
                for cat, duration in categorized.items()
            }
        }
