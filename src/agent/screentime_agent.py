"""
Screen Time Agent for collecting macOS screen time usage data.

Provides tools for querying screen time statistics and generating reports.
"""

import logging
from typing import Dict, Any
from src.automation.screen_time_usage import ScreenTimeCollector

logger = logging.getLogger(__name__)


class ScreenTimeAgent:
    """Agent for screen time data collection and analysis."""

    def __init__(self):
        """Initialize the screen time agent."""
        self.collector = ScreenTimeCollector()
        logger.info("Screen Time Agent initialized")

    async def collect_screen_time_usage(
        self,
        period: str = "weekly",
        weeks_back: int = 1,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """
        Collect screen time usage data.

        Args:
            period: "weekly", "daily", or "category"
            weeks_back: Number of weeks to look back (for weekly)
            days_back: Number of days to look back (for daily)

        Returns:
            Dictionary containing usage statistics
        """
        try:
            if period == "weekly":
                data = self.collector.collect_weekly_usage(weeks_back=weeks_back)
            elif period == "daily":
                data = self.collector.collect_daily_usage(days_back=days_back)
            elif period == "category":
                data = self.collector.collect_category_usage()
            else:
                raise ValueError(f"Unknown period: {period}")

            logger.info(f"Collected {period} screen time usage data")
            return {
                "success": True,
                "data": data
            }

        except Exception as e:
            logger.error(f"Failed to collect screen time usage: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        Get tool definition for LLM.

        Returns:
            Tool definition dictionary
        """
        return {
            "name": "collect_screen_time_usage",
            "description": (
                "Collect screen time usage statistics from macOS. "
                "Returns app usage data, daily breakdowns, and category summaries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["weekly", "daily", "category"],
                        "description": "Type of report to generate",
                        "default": "weekly"
                    },
                    "weeks_back": {
                        "type": "integer",
                        "description": "Number of weeks to look back (for weekly reports)",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 12
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back (for daily reports)",
                        "default": 7,
                        "minimum": 1,
                        "maximum": 90
                    }
                },
                "required": []
            }
        }

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        if tool_name == "collect_screen_time_usage":
            return await self.collect_screen_time_usage(**parameters)
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
