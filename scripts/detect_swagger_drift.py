#!/usr/bin/env python3
"""
Swagger/OpenAPI Doc Drift Detection Script

This script compares OpenAPI specifications against documentation files
to detect drift (outdated documentation that doesn't match the current API spec).

Usage:
    python scripts/detect_swagger_drift.py --spec service_a.yaml --doc payments_api.md
    python scripts/detect_swagger_drift.py --all  # Check all specs against all docs
    python scripts/detect_swagger_drift.py --report  # Generate full drift report

Output:
    - List of parameters in spec but missing from docs
    - List of parameters in docs but removed from spec
    - Endpoint discrepancies
    - Version mismatches
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Paths
SWAGGER_DIR = project_root / "tests" / "fixtures" / "swagger"
DOCS_DIR = SWAGGER_DIR / "docs"


@dataclass
class EndpointInfo:
    """Information about an API endpoint."""
    method: str
    path: str
    operation_id: str
    summary: str
    parameters: Set[str] = field(default_factory=set)
    required_parameters: Set[str] = field(default_factory=set)
    request_body_fields: Set[str] = field(default_factory=set)
    required_body_fields: Set[str] = field(default_factory=set)


@dataclass
class DriftItem:
    """A single drift finding."""
    endpoint: str
    drift_type: str  # "missing_param", "extra_param", "required_mismatch", "description_mismatch"
    field_name: str
    spec_value: Optional[str] = None
    doc_value: Optional[str] = None
    severity: str = "warning"  # "warning", "error", "info"


@dataclass
class DriftReport:
    """Full drift report for a spec/doc comparison."""
    spec_path: str
    doc_path: str
    spec_version: str
    doc_version: Optional[str]
    has_drift: bool = False
    drift_items: List[DriftItem] = field(default_factory=list)
    missing_params: List[str] = field(default_factory=list)
    extra_params: List[str] = field(default_factory=list)
    missing_endpoints: List[str] = field(default_factory=list)
    extra_endpoints: List[str] = field(default_factory=list)
    
    def add_drift(self, item: DriftItem) -> None:
        self.drift_items.append(item)
        self.has_drift = True
        if item.drift_type == "missing_param":
            self.missing_params.append(item.field_name)
        elif item.drift_type == "extra_param":
            self.extra_params.append(item.field_name)


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load a YAML file."""
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_text_file(path: Path) -> str:
    """Load a text/markdown file."""
    if not path.exists():
        return ""
    with open(path, "r") as f:
        return f.read()


def parse_openapi_spec(spec_path: Path) -> Dict[str, EndpointInfo]:
    """
    Parse OpenAPI spec and extract endpoint information.
    
    Returns:
        Dictionary mapping endpoint key (METHOD /path) to EndpointInfo.
    """
    spec = load_yaml_file(spec_path)
    if not spec:
        return {}
    
    endpoints = {}
    paths = spec.get("paths", {})
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            
            key = f"{method.upper()} {path}"
            
            # Extract parameters
            params = set()
            required_params = set()
            for param in details.get("parameters", []):
                param_name = param.get("name", "")
                params.add(param_name)
                if param.get("required", False):
                    required_params.add(param_name)
            
            # Extract request body fields
            body_fields = set()
            required_body_fields = set()
            request_body = details.get("requestBody", {})
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})
            
            if schema.get("type") == "object":
                properties = schema.get("properties", {})
                body_fields = set(properties.keys())
                required_body_fields = set(schema.get("required", []))
            
            endpoints[key] = EndpointInfo(
                method=method.upper(),
                path=path,
                operation_id=details.get("operationId", ""),
                summary=details.get("summary", ""),
                parameters=params,
                required_parameters=required_params,
                request_body_fields=body_fields,
                required_body_fields=required_body_fields,
            )
    
    return endpoints


def parse_doc_parameters(doc_content: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse markdown documentation to extract documented parameters.
    
    Returns:
        Dictionary mapping endpoint key to parameter info.
    """
    endpoints = {}
    
    # Pattern to find endpoint headers like "### Create a Charge" or "`POST /v1/payments/charge`"
    endpoint_pattern = re.compile(r"`(GET|POST|PUT|PATCH|DELETE)\s+(/[^\`]+)`")
    
    # Pattern to find parameter tables
    param_table_pattern = re.compile(
        r"\|\s*`?(\w+)`?\s*\|\s*(\w+)\s*\|\s*(Yes|No|Required|Optional)\s*\|\s*([^|]+)\s*\|",
        re.IGNORECASE
    )
    
    # Find all endpoints mentioned
    current_endpoint = None
    current_params = set()
    current_required = set()
    
    lines = doc_content.split("\n")
    in_param_table = False
    
    for i, line in enumerate(lines):
        # Check for endpoint definition
        endpoint_match = endpoint_pattern.search(line)
        if endpoint_match:
            # Save previous endpoint
            if current_endpoint:
                endpoints[current_endpoint] = {
                    "params": current_params,
                    "required": current_required,
                }
            
            method = endpoint_match.group(1)
            path = endpoint_match.group(2)
            current_endpoint = f"{method} {path}"
            current_params = set()
            current_required = set()
            in_param_table = False
            continue
        
        # Check for parameter table header
        if "Parameter" in line and "|" in line:
            in_param_table = True
            continue
        
        # Parse parameter table rows
        if in_param_table and line.startswith("|"):
            param_match = param_table_pattern.search(line)
            if param_match:
                param_name = param_match.group(1)
                required = param_match.group(3).lower() in ("yes", "required")
                current_params.add(param_name)
                if required:
                    current_required.add(param_name)
        elif in_param_table and not line.strip().startswith("|"):
            in_param_table = False
    
    # Save last endpoint
    if current_endpoint:
        endpoints[current_endpoint] = {
            "params": current_params,
            "required": current_required,
        }
    
    return endpoints


def extract_doc_version(doc_content: str) -> Optional[str]:
    """Extract version from documentation if present."""
    # Look for patterns like "v2.0", "(v2.0)", "version 2.0"
    version_patterns = [
        r"\(v([\d.]+)\)",
        r"version\s+([\d.]+)",
        r"v([\d.]+)",
    ]
    
    for pattern in version_patterns:
        match = re.search(pattern, doc_content, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def detect_drift(spec_path: Path, doc_path: Path) -> DriftReport:
    """
    Compare OpenAPI spec against documentation to detect drift.
    
    Args:
        spec_path: Path to OpenAPI YAML spec
        doc_path: Path to markdown documentation
    
    Returns:
        DriftReport with all findings
    """
    spec = load_yaml_file(spec_path)
    doc_content = load_text_file(doc_path)
    
    spec_version = spec.get("info", {}).get("version", "unknown")
    doc_version = extract_doc_version(doc_content)
    
    report = DriftReport(
        spec_path=str(spec_path),
        doc_path=str(doc_path),
        spec_version=spec_version,
        doc_version=doc_version,
    )
    
    # Check version mismatch
    if doc_version and doc_version != spec_version:
        report.add_drift(DriftItem(
            endpoint="*",
            drift_type="version_mismatch",
            field_name="version",
            spec_value=spec_version,
            doc_value=doc_version,
            severity="warning",
        ))
    
    # Parse both sources
    spec_endpoints = parse_openapi_spec(spec_path)
    doc_endpoints = parse_doc_parameters(doc_content)
    
    # Compare each spec endpoint against docs
    for endpoint_key, spec_info in spec_endpoints.items():
        # Normalize path for comparison (docs might use different formats)
        normalized_keys = [
            endpoint_key,
            endpoint_key.replace("/v1", ""),
            f"{spec_info.method} /v1{spec_info.path}",
        ]
        
        doc_info = None
        for key in normalized_keys:
            if key in doc_endpoints:
                doc_info = doc_endpoints[key]
                break
        
        if not doc_info:
            # Try partial match
            for doc_key in doc_endpoints:
                if spec_info.path in doc_key or doc_key.split()[-1] in spec_info.path:
                    doc_info = doc_endpoints[doc_key]
                    break
        
        if not doc_info:
            report.add_drift(DriftItem(
                endpoint=endpoint_key,
                drift_type="missing_endpoint",
                field_name=endpoint_key,
                spec_value="exists",
                doc_value="missing",
                severity="error",
            ))
            report.missing_endpoints.append(endpoint_key)
            continue
        
        # Compare parameters
        all_spec_params = spec_info.parameters | spec_info.request_body_fields
        all_doc_params = doc_info["params"]
        
        # Parameters in spec but not in docs (doc is outdated)
        for param in all_spec_params - all_doc_params:
            report.add_drift(DriftItem(
                endpoint=endpoint_key,
                drift_type="missing_param",
                field_name=param,
                spec_value="present",
                doc_value="missing",
                severity="error",
            ))
        
        # Parameters in docs but not in spec (doc references removed param)
        for param in all_doc_params - all_spec_params:
            report.add_drift(DriftItem(
                endpoint=endpoint_key,
                drift_type="extra_param",
                field_name=param,
                spec_value="removed",
                doc_value="present",
                severity="warning",
            ))
        
        # Check required status mismatches
        spec_required = spec_info.required_parameters | spec_info.required_body_fields
        doc_required = doc_info["required"]
        
        for param in spec_required - doc_required:
            if param in all_doc_params:
                report.add_drift(DriftItem(
                    endpoint=endpoint_key,
                    drift_type="required_mismatch",
                    field_name=param,
                    spec_value="required",
                    doc_value="optional",
                    severity="warning",
                ))
    
    return report


def print_report(report: DriftReport, verbose: bool = False) -> None:
    """Print drift report to console."""
    print(f"\n{'=' * 60}")
    print(f"  Drift Report: {Path(report.spec_path).name} vs {Path(report.doc_path).name}")
    print(f"{'=' * 60}")
    
    print(f"\nSpec Version: {report.spec_version}")
    print(f"Doc Version:  {report.doc_version or 'unknown'}")
    
    if not report.has_drift:
        print("\n✅ No drift detected - documentation is in sync with spec!")
        return
    
    print(f"\n❌ Drift detected: {len(report.drift_items)} issues found\n")
    
    # Group by severity
    errors = [d for d in report.drift_items if d.severity == "error"]
    warnings = [d for d in report.drift_items if d.severity == "warning"]
    
    if errors:
        print("ERRORS (documentation is missing critical information):")
        for item in errors:
            print(f"  • [{item.endpoint}] {item.drift_type}: {item.field_name}")
            if verbose:
                print(f"      Spec: {item.spec_value}, Doc: {item.doc_value}")
    
    if warnings:
        print("\nWARNINGS (documentation may be outdated):")
        for item in warnings:
            print(f"  • [{item.endpoint}] {item.drift_type}: {item.field_name}")
            if verbose:
                print(f"      Spec: {item.spec_value}, Doc: {item.doc_value}")
    
    # Summary
    print(f"\nSummary:")
    print(f"  Missing parameters in docs: {len(report.missing_params)}")
    if report.missing_params:
        print(f"    → {', '.join(report.missing_params)}")
    print(f"  Extra parameters in docs:   {len(report.extra_params)}")
    if report.extra_params:
        print(f"    → {', '.join(report.extra_params)}")
    print(f"  Missing endpoints in docs:  {len(report.missing_endpoints)}")


def check_all_drift() -> List[DriftReport]:
    """Check all specs against all docs and return reports."""
    reports = []
    
    # Map specs to their likely doc files
    spec_doc_pairs = [
        (SWAGGER_DIR / "service_a.yaml", DOCS_DIR / "payments_api.md"),
        (SWAGGER_DIR / "service_b.yaml", DOCS_DIR / "billing_api.md"),
    ]
    
    for spec_path, doc_path in spec_doc_pairs:
        if spec_path.exists() and doc_path.exists():
            report = detect_drift(spec_path, doc_path)
            reports.append(report)
    
    return reports


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect drift between OpenAPI specs and documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--spec",
        type=str,
        help="Path to OpenAPI spec file (relative to swagger dir or absolute)"
    )
    parser.add_argument(
        "--doc",
        type=str,
        help="Path to documentation file (relative to docs dir or absolute)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all specs against all docs"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate JSON report"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    args = parser.parse_args()
    
    if args.all:
        print("\n🔍 Checking all spec/doc pairs for drift...\n")
        reports = check_all_drift()
        
        drift_found = False
        for report in reports:
            print_report(report, args.verbose)
            if report.has_drift:
                drift_found = True
        
        if args.report:
            report_data = []
            for report in reports:
                report_data.append({
                    "spec": report.spec_path,
                    "doc": report.doc_path,
                    "spec_version": report.spec_version,
                    "doc_version": report.doc_version,
                    "has_drift": report.has_drift,
                    "missing_params": report.missing_params,
                    "extra_params": report.extra_params,
                    "drift_count": len(report.drift_items),
                })
            print("\n" + json.dumps(report_data, indent=2))
        
        return 1 if drift_found else 0
    
    elif args.spec and args.doc:
        # Resolve paths
        spec_path = Path(args.spec)
        if not spec_path.is_absolute():
            spec_path = SWAGGER_DIR / args.spec
        
        doc_path = Path(args.doc)
        if not doc_path.is_absolute():
            doc_path = DOCS_DIR / args.doc
        
        if not spec_path.exists():
            print(f"❌ Spec file not found: {spec_path}")
            return 1
        
        if not doc_path.exists():
            print(f"❌ Doc file not found: {doc_path}")
            return 1
        
        report = detect_drift(spec_path, doc_path)
        print_report(report, args.verbose)
        
        if args.report:
            print("\n" + json.dumps({
                "spec": report.spec_path,
                "doc": report.doc_path,
                "has_drift": report.has_drift,
                "missing_params": report.missing_params,
                "extra_params": report.extra_params,
            }, indent=2))
        
        return 1 if report.has_drift else 0
    
    else:
        # Default: run --all
        print("No arguments provided. Running --all to check all specs...\n")
        reports = check_all_drift()
        
        drift_found = False
        for report in reports:
            print_report(report, args.verbose)
            if report.has_drift:
                drift_found = True
        
        return 1 if drift_found else 0


if __name__ == "__main__":
    sys.exit(main())

