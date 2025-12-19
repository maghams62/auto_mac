"""
Tool Chain Catalog Manager
Automatically updates tool_chains.yml with failure patterns and generates planner tips.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ToolChainCatalog:
    """Manages the tool chain catalog and failure pattern learning."""

    def __init__(self, catalog_file: str = "telemetry/tool_chains.yml"):
        self.catalog_file = Path(__file__).parent / catalog_file
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        """Load the catalog from YAML file."""
        if self.catalog_file.exists():
            try:
                with open(self.catalog_file, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load catalog: {e}")
                return self._create_default_catalog()
        else:
            return self._create_default_catalog()

    def _create_default_catalog(self) -> Dict[str, Any]:
        """Create a default empty catalog structure."""
        return {
            "canonical_chains": {},
            "failure_patterns": {},
            "dynamic_failures": []
        }

    def _save_catalog(self):
        """Save the catalog to YAML file."""
        try:
            self.catalog_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.catalog_file, 'w') as f:
                yaml.dump(self.catalog, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.error(f"Failed to save catalog: {e}")

    def add_failure_pattern(self, pattern_name: str, incident_data: Dict[str, Any]):
        """Add a new failure pattern to the catalog."""
        if "dynamic_failures" not in self.catalog:
            self.catalog["dynamic_failures"] = []

        # Create failure entry
        failure_entry = {
            "pattern_name": pattern_name,
            "detected_at": datetime.now().isoformat(),
            "incident": incident_data,
            "tool_chain": self._extract_tool_chain_from_incident(incident_data),
            "avoidance_tip": self._generate_avoidance_tip(pattern_name, incident_data)
        }

        self.catalog["dynamic_failures"].append(failure_entry)

        # Limit to last 100 failures to prevent file from growing too large
        if len(self.catalog["dynamic_failures"]) > 100:
            self.catalog["dynamic_failures"] = self.catalog["dynamic_failures"][-100:]

        self._save_catalog()
        logger.info(f"Added failure pattern '{pattern_name}' to catalog")

    def _extract_tool_chain_from_incident(self, incident_data: Dict[str, Any]) -> List[str]:
        """Extract the tool chain that led to the failure."""
        context = incident_data.get("context", {})
        tool_name = context.get("tool_name", "unknown")

        # For now, just return the failing tool
        # In the future, this could trace back through telemetry to find the full chain
        return [tool_name] if tool_name != "unknown" else []

    def _generate_avoidance_tip(self, pattern_name: str, incident_data: Dict[str, Any]) -> str:
        """Generate an avoidance tip based on the failure pattern."""
        tips = {
            "missing_reply": "Ensure reply_to_user is included as final step in all plans",
            "missing_doc_path": "Verify search_documents returns valid doc_path in best_result",
            "agent_import_error": "Validate agent registry imports on startup",
            "websocket_error": "Add connection retry logic with exponential backoff"
        }

        return tips.get(pattern_name, f"Avoid pattern: {pattern_name}")

    def get_recent_failure_tips(self, limit: int = 5) -> List[str]:
        """Get recent failure avoidance tips for planner prompts."""
        dynamic_failures = self.catalog.get("dynamic_failures", [])

        # Get the most recent failures
        recent_failures = sorted(
            dynamic_failures,
            key=lambda x: x.get("detected_at", ""),
            reverse=True
        )[:limit]

        tips = []
        for failure in recent_failures:
            tip = failure.get("avoidance_tip", "")
            if tip:
                tips.append(f"- {tip}")

        return tips

    def get_canonical_chain(self, chain_name: str) -> Optional[Dict[str, Any]]:
        """Get a canonical tool chain by name."""
        return self.catalog.get("canonical_chains", {}).get(chain_name)

    def get_failure_pattern(self, pattern_name: str) -> Optional[Dict[str, Any]]:
        """Get a known failure pattern by name."""
        return self.catalog.get("failure_patterns", {}).get(pattern_name)

    def generate_planner_prompt_tips(self) -> str:
        """Generate formatted tips for inclusion in planner prompts."""
        tips = self.get_recent_failure_tips()

        if not tips:
            return ""

        prompt_section = "\n".join([
            "## Recent Failure Avoidance Tips",
            "Based on recent incidents, remember to:",
            *tips,
            ""
        ])

        return prompt_section

    def find_similar_failures(self, current_incident: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar historical failures for pattern matching."""
        dynamic_failures = self.catalog.get("dynamic_failures", [])
        similar = []

        current_pattern = current_incident.get("pattern")
        current_tool = current_incident.get("context", {}).get("tool_name")

        for failure in dynamic_failures:
            if (failure.get("pattern_name") == current_pattern or
                failure.get("tool_chain") == [current_tool]):
                similar.append(failure)

        return similar[-5:]  # Return last 5 similar failures

# Global catalog instance
_catalog_instance = None

def get_catalog() -> ToolChainCatalog:
    """Get the global catalog instance."""
    global _catalog_instance
    if _catalog_instance is None:
        _catalog_instance = ToolChainCatalog()
    return _catalog_instance

def update_catalog_with_failure(pattern_name: str, incident_data: Dict[str, Any]):
    """Convenience function to update catalog with a failure."""
    catalog = get_catalog()
    catalog.add_failure_pattern(pattern_name, incident_data)

def get_planner_failure_tips() -> str:
    """Get formatted failure tips for planner prompts."""
    catalog = get_catalog()
    return catalog.generate_planner_prompt_tips()
