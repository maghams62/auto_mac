"""
API Docs Agent - Self-evolving API documentation management.

This agent implements the Oqoqo-style self-evolving documentation pattern:
- Reads the current API spec (docs/api-spec.yaml)
- Compares against actual code (api_server.py)
- Detects drift using LLM-based semantic diff
- Proposes and applies updates to keep docs in sync

Tools:
- read_api_spec: Read the current OpenAPI spec
- read_api_code: Read the api_server.py code
- check_api_drift: Detect divergence between code and spec
- apply_spec_update: Apply proposed changes to the spec
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
API_SPEC_PATH = PROJECT_ROOT / "docs" / "api-spec.yaml"
API_SERVER_PATH = PROJECT_ROOT / "api_server.py"


@tool
def read_api_spec() -> Dict[str, Any]:
    """
    Read the current OpenAPI specification from docs/api-spec.yaml.
    
    Returns the raw YAML content and parsed structure for analysis.
    This represents the "human-facing documentation" that may drift from code.
    
    Returns:
        Dictionary with:
        - content: Raw YAML string
        - path: File path
        - exists: Whether the file exists
        - error: Error message if any
    """
    logger.info("[APIDOCS AGENT] Reading API spec from %s", API_SPEC_PATH)
    
    try:
        if not API_SPEC_PATH.exists():
            return {
                "exists": False,
                "path": str(API_SPEC_PATH),
                "content": None,
                "error": f"API spec file not found at {API_SPEC_PATH}"
            }
        
        content = API_SPEC_PATH.read_text(encoding="utf-8")
        
        # Also parse YAML for structured access
        try:
            import yaml
            parsed = yaml.safe_load(content)
        except Exception as e:
            parsed = None
            logger.warning("[APIDOCS AGENT] Failed to parse YAML: %s", e)
        
        return {
            "exists": True,
            "path": str(API_SPEC_PATH),
            "content": content,
            "parsed": parsed,
            "line_count": len(content.splitlines()),
            "error": None
        }
        
    except Exception as e:
        logger.error("[APIDOCS AGENT] Error reading API spec: %s", e)
        return {
            "exists": False,
            "path": str(API_SPEC_PATH),
            "content": None,
            "error": str(e)
        }


@tool
def read_api_code(include_full: bool = False) -> Dict[str, Any]:
    """
    Read the api_server.py source code for analysis.
    
    By default, extracts only the endpoint definitions (decorators and signatures)
    to reduce token usage. Set include_full=True for complete code.
    
    Args:
        include_full: If True, return full file content. If False, extract endpoints only.
    
    Returns:
        Dictionary with:
        - content: Code content (full or extracted endpoints)
        - path: File path
        - endpoints: List of detected endpoint signatures
        - error: Error message if any
    """
    logger.info("[APIDOCS AGENT] Reading API server code from %s", API_SERVER_PATH)
    
    try:
        if not API_SERVER_PATH.exists():
            return {
                "exists": False,
                "path": str(API_SERVER_PATH),
                "content": None,
                "error": f"API server file not found at {API_SERVER_PATH}"
            }
        
        content = API_SERVER_PATH.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        # Extract endpoint definitions
        endpoints = []
        current_endpoint = None
        
        for i, line in enumerate(lines):
            # Detect FastAPI route decorators
            if line.strip().startswith("@app.") and any(
                method in line for method in [".get(", ".post(", ".put(", ".delete(", ".patch("]
            ):
                # Extract the route path and method
                import re
                match = re.search(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', line)
                if match:
                    method = match.group(1).upper()
                    path = match.group(2)
                    
                    # Look ahead for the function signature and docstring
                    func_line = ""
                    docstring = ""
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if lines[j].strip().startswith("async def ") or lines[j].strip().startswith("def "):
                            func_line = lines[j].strip()
                            # Check for docstring
                            if j + 1 < len(lines) and '"""' in lines[j + 1]:
                                docstring = lines[j + 1].strip().strip('"""').strip()
                            break
                    
                    endpoints.append({
                        "method": method,
                        "path": path,
                        "line_number": i + 1,
                        "function": func_line,
                        "docstring": docstring,
                        "decorator": line.strip()
                    })
        
        result = {
            "exists": True,
            "path": str(API_SERVER_PATH),
            "endpoints": endpoints,
            "endpoint_count": len(endpoints),
            "total_lines": len(lines),
            "error": None
        }
        
        if include_full:
            result["content"] = content
        else:
            # Build a summary of endpoints for LLM analysis
            endpoint_summary = []
            for ep in endpoints:
                endpoint_summary.append(
                    f"{ep['method']} {ep['path']}\n"
                    f"  Line {ep['line_number']}: {ep['function']}\n"
                    f"  Doc: {ep['docstring']}"
                )
            result["content"] = "\n\n".join(endpoint_summary)
        
        return result
        
    except Exception as e:
        logger.error("[APIDOCS AGENT] Error reading API code: %s", e)
        return {
            "exists": False,
            "path": str(API_SERVER_PATH),
            "content": None,
            "endpoints": [],
            "error": str(e)
        }


@tool
def write_api_spec(content: str, backup: bool = True) -> Dict[str, Any]:
    """
    Write updated content to the API spec file.
    
    This is used to apply proposed updates after user approval.
    Creates a backup of the existing spec before overwriting.
    
    Args:
        content: New YAML content for the spec
        backup: If True, create a .backup file before overwriting
    
    Returns:
        Dictionary with:
        - success: Whether the write succeeded
        - path: File path
        - backup_path: Path to backup file (if created)
        - error: Error message if any
    """
    logger.info("[APIDOCS AGENT] Writing updated API spec to %s", API_SPEC_PATH)
    
    try:
        # Validate YAML before writing
        import yaml
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return {
                "success": False,
                "path": str(API_SPEC_PATH),
                "error": f"Invalid YAML: {e}"
            }
        
        backup_path = None
        if backup and API_SPEC_PATH.exists():
            backup_path = API_SPEC_PATH.with_suffix(".yaml.backup")
            existing_content = API_SPEC_PATH.read_text(encoding="utf-8")
            backup_path.write_text(existing_content, encoding="utf-8")
            logger.info("[APIDOCS AGENT] Created backup at %s", backup_path)
        
        # Write new content
        API_SPEC_PATH.write_text(content, encoding="utf-8")
        
        return {
            "success": True,
            "path": str(API_SPEC_PATH),
            "backup_path": str(backup_path) if backup_path else None,
            "error": None
        }
        
    except Exception as e:
        logger.error("[APIDOCS AGENT] Error writing API spec: %s", e)
        return {
            "success": False,
            "path": str(API_SPEC_PATH),
            "error": str(e)
        }


@tool
def get_api_spec_url() -> Dict[str, Any]:
    """
    Get the URL to view the API documentation.
    
    Returns URLs for:
    - Swagger UI (interactive docs)
    - ReDoc (alternative docs view)
    - Raw OpenAPI JSON
    
    Returns:
        Dictionary with documentation URLs
    """
    base_url = "http://localhost:8000"
    
    return {
        "swagger_ui": f"{base_url}/docs",
        "redoc": f"{base_url}/redoc",
        "openapi_json": f"{base_url}/openapi.json",
        "spec_file": str(API_SPEC_PATH),
        "message": "FastAPI auto-generates docs at /docs. The manual spec is at docs/api-spec.yaml"
    }


# Tool registry for the agent
APIDOCS_AGENT_TOOLS = [
    read_api_spec,
    read_api_code,
    write_api_spec,
    get_api_spec_url,
]


# Agent hierarchy documentation
APIDOCS_AGENT_HIERARCHY = """
API Docs Agent Hierarchy:
=========================

PURPOSE: Self-evolving API documentation (Oqoqo pattern)
- Detects drift between code (api_server.py) and docs (docs/api-spec.yaml)
- Uses LLM to semantically understand API changes
- Proposes and applies documentation updates

TOOLS:
├─ read_api_spec → Read current OpenAPI spec (docs/api-spec.yaml)
├─ read_api_code → Extract endpoint definitions from api_server.py
├─ write_api_spec → Apply approved updates to the spec
└─ get_api_spec_url → Get URLs to view documentation

TYPICAL WORKFLOW:
1. User types `/apidocs check` or system detects code change
2. read_api_code() extracts current endpoints from code
3. read_api_spec() loads the documented spec
4. LLM compares and identifies drift
5. If drift found, propose update with explanation
6. User approves → write_api_spec() applies changes
7. Confirm with link to view updated docs

DRIFT TYPES DETECTED:
- New endpoint added in code but not documented
- Endpoint removed from code but still in docs
- Parameter added/removed/changed type
- Response schema changed
- HTTP method changed
- Path changed
"""


class ApidocsAgent:
    """
    API Documentation Agent - Mini-orchestrator for self-evolving docs.
    
    Implements the Oqoqo pattern:
    - Code is the source of truth
    - Docs should reflect code accurately
    - When they diverge, the system detects and offers to heal
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = {tool.name: tool for tool in APIDOCS_AGENT_TOOLS}
        logger.info(f"[APIDOCS AGENT] Initialized with {len(self.tools)} tools")
    
    def get_tools(self) -> List:
        """Get all apidocs agent tools."""
        return APIDOCS_AGENT_TOOLS
    
    def get_hierarchy(self) -> str:
        """Get apidocs agent hierarchy documentation."""
        return APIDOCS_AGENT_HIERARCHY
    
    def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an apidocs agent tool."""
        if tool_name not in self.tools:
            return {
                "error": True,
                "error_type": "ToolNotFound",
                "error_message": f"Apidocs agent tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }
        
        tool = self.tools[tool_name]
        logger.info(f"[APIDOCS AGENT] Executing: {tool_name}")
        
        try:
            result = tool.invoke(inputs)
            return result
        except Exception as e:
            logger.error(f"[APIDOCS AGENT] Execution error: {e}")
            return {
                "error": True,
                "error_type": "ExecutionError",
                "error_message": str(e),
                "retry_possible": False
            }

