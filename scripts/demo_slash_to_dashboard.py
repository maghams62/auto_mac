#!/usr/bin/env python3
"""
Run a Cerebros graph query and automatically promote the result to an incident so it
shows up in the Oqoqo dashboard. Useful for demos that need a fresh slash → dashboard flow.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

import requests


def post_json(url: str, payload: Dict[str, Any], *, timeout: int = 60) -> Dict[str, Any]:
    response = requests.post(url, json=payload, timeout=timeout)
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Request to {url} failed ({response.status_code}): {detail}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Slash → dashboard demo helper")
    parser.add_argument("--query", required=True, help="Slash Cerebros prompt to run")
    parser.add_argument(
        "--component-id",
        default="docs.payments",
        help="Component id hint for the graph reasoner (default: docs.payments)",
    )
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8000",
        help="Cerebros API base (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--dashboard-port",
        default="3000",
        help="Port where the Oqoqo dashboard is running (default: 3000)",
    )
    args = parser.parse_args()

    graph_payload: Dict[str, Any] = {"query": args.query}
    if args.component_id:
        graph_payload["componentId"] = args.component_id

    print(f"[demo] Running Cerebros graph query: {json.dumps(graph_payload)}")
    graph_result = post_json(f"{args.api_base}/api/graph/query", graph_payload)

    investigation_id = graph_result.get("investigation_id")
    brain_url = graph_result.get("url")
    candidate = graph_result.get("incident_candidate")
    if not isinstance(candidate, dict):
        raise RuntimeError("Graph response did not include incident_candidate.")

    print(f"[demo] Investigation ID: {investigation_id}")
    if brain_url:
        print(f"[demo] Brain trace URL: {brain_url}")

    severity = candidate.get("severity") or "medium"
    promote_payload = {
        "incident_candidate": candidate,
        "severity": severity,
        "status": candidate.get("status") or "open",
    }
    incident_result = post_json(f"{args.api_base}/api/incidents", promote_payload)
    incident_id: Optional[str] = incident_result.get("id")
    if not incident_id:
        raise RuntimeError(f"Incident creation response missing id: {incident_result}")

    dashboard_url = f"http://localhost:{args.dashboard_port}/incidents/{incident_id}"
    print()
    print(f"[demo] Incident created: {incident_id}")
    print(f"[demo] Dashboard detail: {dashboard_url}")
    print(f"[demo] Projects overview: http://localhost:{args.dashboard_port}/projects")
    if brain_url:
        print(f"[demo] Cerebros deep link: {brain_url}")
    elif candidate.get("brainTraceUrl"):
        print(f"[demo] Brain trace: http://localhost:{args.dashboard_port}{candidate['brainTraceUrl']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

