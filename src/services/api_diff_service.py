"""
API Diff Service - LLM-based semantic diff for API documentation.

This service implements the core Oqoqo pattern:
1. Extract API surface from code using LLM understanding
2. Compare code API surface against documented spec
3. Identify meaningful drift (not just text changes)
4. Generate human-readable change summaries
5. Propose spec updates that align with code

The key insight is using LLM for semantic understanding rather than
syntactic diff - the LLM understands what constitutes an API change
(new parameter, type change, etc.) vs irrelevant code changes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of API changes that can be detected."""
    ENDPOINT_ADDED = "endpoint_added"
    ENDPOINT_REMOVED = "endpoint_removed"
    PARAMETER_ADDED = "parameter_added"
    PARAMETER_REMOVED = "parameter_removed"
    PARAMETER_TYPE_CHANGED = "parameter_type_changed"
    PARAMETER_REQUIRED_CHANGED = "parameter_required_changed"
    RESPONSE_CHANGED = "response_changed"
    METHOD_CHANGED = "method_changed"
    PATH_CHANGED = "path_changed"
    DESCRIPTION_CHANGED = "description_changed"


class Severity(str, Enum):
    """Severity of the API change."""
    BREAKING = "breaking"  # Requires client changes
    NON_BREAKING = "non_breaking"  # Backward compatible
    COSMETIC = "cosmetic"  # Documentation only


@dataclass
class ApiChange:
    """Represents a single API change detected between code and spec."""
    change_type: ChangeType
    severity: Severity
    endpoint: str  # e.g., "POST /api/users"
    description: str  # Human-readable description
    code_value: Optional[str] = None  # What the code says
    spec_value: Optional[str] = None  # What the spec says
    suggested_fix: Optional[str] = None  # How to update the spec

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_type.value,
            "severity": self.severity.value,
            "endpoint": self.endpoint,
            "description": self.description,
            "code_value": self.code_value,
            "spec_value": self.spec_value,
            "suggested_fix": self.suggested_fix
        }


@dataclass
class DriftReport:
    """Complete drift analysis report."""
    has_drift: bool
    changes: List[ApiChange]
    summary: str  # Human-readable summary
    proposed_spec: Optional[str] = None  # Updated YAML if drift found
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_drift": self.has_drift,
            "changes": [c.to_dict() for c in self.changes],
            "summary": self.summary,
            "proposed_spec": self.proposed_spec,
            "change_count": len(self.changes),
            "breaking_changes": sum(1 for c in self.changes if c.severity == Severity.BREAKING),
            "non_breaking_changes": sum(1 for c in self.changes if c.severity == Severity.NON_BREAKING)
        }


class ApiDiffService:
    """
    LLM-based semantic diff service for API documentation.
    
    Uses Claude/GPT to understand API changes at a semantic level,
    rather than doing simple text diffing.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the diff service.
        
        Args:
            config: Application configuration with OpenAI settings
        """
        self.config = config
        logger.info("[API DIFF SERVICE] Initialized")
    
    def _get_llm(self, temperature: float = 0.1) -> ChatOpenAI:
        """Get configured LLM instance."""
        from src.utils import get_llm_params
        params = get_llm_params(self.config, default_temperature=temperature, max_tokens=4000)
        return ChatOpenAI(**params)
    
    def extract_api_surface(self, code: str) -> Dict[str, Any]:
        """
        Use LLM to extract the API surface from Python/FastAPI code.
        
        This is the key semantic understanding step - the LLM reads the code
        and extracts structured information about endpoints, parameters, etc.
        
        Args:
            code: Source code content (api_server.py or endpoint summaries)
        
        Returns:
            Structured API surface description
        """
        logger.info("[API DIFF SERVICE] Extracting API surface from code")
        
        llm = self._get_llm(temperature=0.0)
        
        system_prompt = """You are an API documentation expert. Analyze the given FastAPI/Python code 
and extract the API surface in structured JSON format.

For each endpoint, extract:
- method: HTTP method (GET, POST, PUT, DELETE, PATCH)
- path: URL path (e.g., "/api/users")
- operation_id: Function name
- summary: Brief description from docstring
- parameters: List of query/path/body parameters with name, type, required flag
- responses: Expected response codes and schemas

Output valid JSON only, no markdown or explanation."""

        human_prompt = f"""Analyze this FastAPI code and extract the API surface:

```python
{code[:15000]}  # Truncate if too long
```

Return a JSON object with this structure:
{{
  "endpoints": [
    {{
      "method": "GET",
      "path": "/api/example",
      "operation_id": "get_example",
      "summary": "Description here",
      "parameters": [
        {{"name": "param1", "type": "string", "required": true, "in": "query"}}
      ],
      "responses": ["200", "500"]
    }}
  ]
}}"""

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            
            # Parse JSON from response
            content = response.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"[API DIFF SERVICE] Failed to parse LLM response as JSON: {e}")
            return {"endpoints": [], "error": str(e)}
        except Exception as e:
            logger.error(f"[API DIFF SERVICE] Error extracting API surface: {e}")
            return {"endpoints": [], "error": str(e)}
    
    def compare_surfaces(
        self, 
        code_surface: Dict[str, Any], 
        spec_content: str
    ) -> List[ApiChange]:
        """
        Use LLM to compare code API surface against documented spec.
        
        This is semantic comparison - the LLM understands that adding
        a required parameter is a breaking change, etc.
        
        Args:
            code_surface: Extracted API surface from code
            spec_content: OpenAPI YAML spec content
        
        Returns:
            List of detected changes
        """
        logger.info("[API DIFF SERVICE] Comparing API surfaces")
        
        llm = self._get_llm(temperature=0.0)
        
        system_prompt = """You are an API compatibility expert. Compare the actual API (from code) 
against the documented API spec and identify all differences.

For each difference, determine:
1. change_type: One of: endpoint_added, endpoint_removed, parameter_added, parameter_removed, 
   parameter_type_changed, parameter_required_changed, response_changed, method_changed, 
   path_changed, description_changed
2. severity: "breaking" (requires client changes), "non_breaking" (backward compatible), 
   or "cosmetic" (docs only)
3. endpoint: The affected endpoint (e.g., "POST /api/users")
4. description: Human-readable explanation of the change
5. code_value: What the code currently has
6. spec_value: What the spec documents

Output valid JSON array only."""

        human_prompt = f"""Compare these two API definitions:

## ACTUAL API (from code - this is the source of truth):
```json
{json.dumps(code_surface, indent=2)[:8000]}
```

## DOCUMENTED API (spec - may be out of date):
```yaml
{spec_content[:8000]}
```

Find all differences where the spec doesn't match the code.
Return a JSON array of changes:
[
  {{
    "change_type": "parameter_added",
    "severity": "breaking",
    "endpoint": "POST /api/users",
    "description": "New required parameter 'invite_code' added",
    "code_value": "invite_code: string (required)",
    "spec_value": "not documented"
  }}
]

Return empty array [] if no differences found."""

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            changes_data = json.loads(content)
            
            changes = []
            for c in changes_data:
                try:
                    changes.append(ApiChange(
                        change_type=ChangeType(c.get("change_type", "description_changed")),
                        severity=Severity(c.get("severity", "cosmetic")),
                        endpoint=c.get("endpoint", "unknown"),
                        description=c.get("description", ""),
                        code_value=c.get("code_value"),
                        spec_value=c.get("spec_value"),
                        suggested_fix=c.get("suggested_fix")
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"[API DIFF SERVICE] Skipping invalid change: {e}")
            
            return changes
            
        except json.JSONDecodeError as e:
            logger.error(f"[API DIFF SERVICE] Failed to parse comparison result: {e}")
            return []
        except Exception as e:
            logger.error(f"[API DIFF SERVICE] Error comparing surfaces: {e}")
            return []
    
    def generate_updated_spec(
        self, 
        current_spec: str, 
        changes: List[ApiChange],
        code_surface: Dict[str, Any]
    ) -> str:
        """
        Use LLM to generate an updated spec that reflects the code.
        
        Args:
            current_spec: Current OpenAPI YAML content
            changes: List of detected changes
            code_surface: Extracted API surface from code
        
        Returns:
            Updated OpenAPI YAML content
        """
        logger.info("[API DIFF SERVICE] Generating updated spec")
        
        if not changes:
            return current_spec
        
        llm = self._get_llm(temperature=0.0)
        
        changes_desc = "\n".join([
            f"- {c.endpoint}: {c.description} (code: {c.code_value}, spec: {c.spec_value})"
            for c in changes
        ])
        
        system_prompt = """You are an OpenAPI specification expert. Update the given OpenAPI YAML spec 
to match the actual API from code. Make minimal changes - only update what's necessary to fix the drift.

Preserve:
- Existing descriptions and examples where still accurate
- YAML formatting and structure
- Comments if present

Output the complete updated YAML spec only, no explanation."""

        human_prompt = f"""Update this OpenAPI spec to fix the following drift:

## CHANGES NEEDED:
{changes_desc}

## CURRENT SPEC:
```yaml
{current_spec}
```

## ACTUAL API (source of truth):
```json
{json.dumps(code_surface, indent=2)[:6000]}
```

Output the complete updated YAML spec:"""

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            
            content = response.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first and last lines (``` markers)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)
            
            return content
            
        except Exception as e:
            logger.error(f"[API DIFF SERVICE] Error generating updated spec: {e}")
            return current_spec
    
    def generate_summary(self, changes: List[ApiChange]) -> str:
        """
        Generate a human-readable summary of the changes.
        
        Args:
            changes: List of detected changes
        
        Returns:
            Markdown-formatted summary
        """
        if not changes:
            return "No drift detected. API documentation is in sync with code."
        
        breaking = [c for c in changes if c.severity == Severity.BREAKING]
        non_breaking = [c for c in changes if c.severity == Severity.NON_BREAKING]
        cosmetic = [c for c in changes if c.severity == Severity.COSMETIC]
        
        summary_parts = [f"**API Documentation Drift Detected** ({len(changes)} changes)"]
        
        if breaking:
            summary_parts.append(f"\n### Breaking Changes ({len(breaking)})")
            for c in breaking:
                summary_parts.append(f"- **{c.endpoint}**: {c.description}")
        
        if non_breaking:
            summary_parts.append(f"\n### Non-Breaking Changes ({len(non_breaking)})")
            for c in non_breaking:
                summary_parts.append(f"- **{c.endpoint}**: {c.description}")
        
        if cosmetic:
            summary_parts.append(f"\n### Documentation Updates ({len(cosmetic)})")
            for c in cosmetic:
                summary_parts.append(f"- **{c.endpoint}**: {c.description}")
        
        return "\n".join(summary_parts)
    
    def check_drift(self, code_content: str, spec_content: str) -> DriftReport:
        """
        Main entry point: check for drift between code and spec.
        
        This orchestrates the full semantic diff pipeline:
        1. Extract API surface from code
        2. Compare against spec
        3. Generate summary and proposed update
        
        Args:
            code_content: Source code (api_server.py content or endpoint summary)
            spec_content: OpenAPI YAML spec content
        
        Returns:
            Complete drift report with changes and proposed fix
        """
        logger.info("[API DIFF SERVICE] Checking for API drift")
        
        # Step 1: Extract API surface from code
        code_surface = self.extract_api_surface(code_content)
        
        if "error" in code_surface:
            return DriftReport(
                has_drift=False,
                changes=[],
                summary=f"Error analyzing code: {code_surface['error']}",
                proposed_spec=None
            )
        
        # Step 2: Compare against spec
        changes = self.compare_surfaces(code_surface, spec_content)
        
        # Step 3: Generate summary
        summary = self.generate_summary(changes)
        
        # Step 4: Generate updated spec if drift found
        proposed_spec = None
        if changes:
            proposed_spec = self.generate_updated_spec(spec_content, changes, code_surface)
        
        return DriftReport(
            has_drift=len(changes) > 0,
            changes=changes,
            summary=summary,
            proposed_spec=proposed_spec
        )


# Singleton instance for reuse
_diff_service: Optional[ApiDiffService] = None


def get_api_diff_service(config: Dict[str, Any]) -> ApiDiffService:
    """Get or create the API diff service singleton."""
    global _diff_service
    if _diff_service is None:
        _diff_service = ApiDiffService(config)
    return _diff_service

