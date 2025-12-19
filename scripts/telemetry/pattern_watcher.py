#!/usr/bin/env python3
"""
Pattern Watcher: Monitors logs for failure patterns and sends alerts.

Watches api_server.log and telemetry traces for critical failure patterns:
- [FINALIZE] ❌ No reply found
- WebSocket queue warnings
- Tool execution errors
- Missing agent classes

Sends webhook alerts with failing tool chains and conversation snippets.
Persists incidents to telemetry/incidents.jsonl for prompt fine-tuning.
"""

import os
import sys
import time
import json
import logging
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import re
import threading

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from telemetry import log_structured
from telemetry.catalog_manager import update_catalog_with_failure

logger = logging.getLogger(__name__)

class PatternWatcher:
    """Monitors logs for failure patterns and sends alerts."""

    def __init__(self, log_file: str = "api_server.log", incidents_file: str = "telemetry/incidents.jsonl"):
        self.log_file = Path(project_root) / log_file
        self.incidents_file = Path(project_root) / incidents_file
        self.incidents_file.parent.mkdir(parents=True, exist_ok=True)

        # Failure patterns to monitor
        self.failure_patterns = {
            "missing_reply": {
                "pattern": r"\[FINALIZE\]\s+❌.*No reply found",
                "severity": "critical",
                "description": "Agent completed without sending reply to user",
                "webhook_enabled": True
            },
            "websocket_queue_full": {
                "pattern": r"WebSocket.*queue.*full|queue.*overflow",
                "severity": "high",
                "description": "WebSocket message queue overflow",
                "webhook_enabled": True
            },
            "tool_execution_error": {
                "pattern": r"Tool.*execution.*error|tool.*failed",
                "severity": "medium",
                "description": "Tool execution failed",
                "webhook_enabled": False
            },
            "missing_agent_class": {
                "pattern": r"cannot import name.*Agent|No module named.*agent",
                "severity": "high",
                "description": "Missing agent class import",
                "webhook_enabled": True
            },
            "websocket_connection_failed": {
                "pattern": r"WebSocket.*error.*not connected|ConnectionManager.*failed",
                "severity": "medium",
                "description": "WebSocket connection issues",
                "webhook_enabled": False
            }
        }

        # Alert configuration
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        self.alert_cooldown_minutes = int(os.getenv("ALERT_COOLDOWN_MINUTES", "5"))
        self.last_alerts: Dict[str, datetime] = {}

        # Monitoring state
        self.last_position = 0
        self.running = False

        logger.info(f"[PATTERN WATCHER] Initialized monitoring {self.log_file}")

    def start(self):
        """Start the pattern watcher."""
        self.running = True
        logger.info("[PATTERN WATCHER] Starting log monitoring...")

        try:
            # Seek to end of file initially
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    f.seek(0, 2)  # Seek to end
                    self.last_position = f.tell()

            while self.running:
                self._check_patterns()
                time.sleep(1)  # Check every second

        except KeyboardInterrupt:
            logger.info("[PATTERN WATCHER] Stopped by user")
        except Exception as e:
            logger.error(f"[PATTERN WATCHER] Error: {e}")
        finally:
            self.running = False

    def stop(self):
        """Stop the pattern watcher."""
        self.running = False
        logger.info("[PATTERN WATCHER] Stopping...")

    def _check_patterns(self):
        """Check log file for failure patterns."""
        if not self.log_file.exists():
            return

        try:
            with open(self.log_file, 'r') as f:
                f.seek(self.last_position)
                lines = f.readlines()
                self.last_position = f.tell()

            if not lines:
                return

            # Process each new line
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                for pattern_name, config in self.failure_patterns.items():
                    if re.search(config["pattern"], line, re.IGNORECASE):
                        self._handle_pattern_match(pattern_name, config, line)

        except Exception as e:
            logger.error(f"[PATTERN WATCHER] Error reading log: {e}")

    def _handle_pattern_match(self, pattern_name: str, config: Dict[str, Any], line: str):
        """Handle a pattern match by logging, alerting, and persisting."""
        timestamp = datetime.now()

        # Check cooldown
        if pattern_name in self.last_alerts:
            time_since_last = timestamp - self.last_alerts[pattern_name]
            if time_since_last < timedelta(minutes=self.alert_cooldown_minutes):
                logger.debug(f"[PATTERN WATCHER] Skipping {pattern_name} due to cooldown")
                return

        # Extract context around the error
        context = self._extract_context(line)

        # Create incident record
        incident = {
            "timestamp": timestamp.isoformat(),
            "pattern": pattern_name,
            "severity": config["severity"],
            "description": config["description"],
            "matched_line": line,
            "context": context,
            "log_file": str(self.log_file),
            "correlation_id": context.get("correlation_id"),
            "session_id": context.get("session_id")
        }

        # Persist incident
        self._persist_incident(incident)

        # Send alert if enabled
        if config["webhook_enabled"] and self.webhook_url:
            self._send_webhook_alert(incident)

        # Update last alert time
        self.last_alerts[pattern_name] = timestamp

        # Update tool chain catalog with failure pattern
        try:
            update_catalog_with_failure(pattern_name, incident)
        except Exception as e:
            logger.error(f"[PATTERN WATCHER] Failed to update catalog: {e}")

        # Log structured event
        log_structured("warning", f"Failure pattern detected: {pattern_name}",
                      pattern=pattern_name, severity=config["severity"],
                      matched_line=line[:200], correlation_id=context.get("correlation_id"))

    def _extract_context(self, matched_line: str) -> Dict[str, Any]:
        """Extract contextual information around the matched line."""
        context = {}

        # Extract correlation ID
        correlation_match = re.search(r"correlation[_-]id[:\s]*([a-zA-Z0-9\-:]+)", matched_line, re.IGNORECASE)
        if correlation_match:
            context["correlation_id"] = correlation_match.group(1)

        # Extract session ID
        session_match = re.search(r"session[_-]id[:\s]*([a-zA-Z0-9\-]+)", matched_line, re.IGNORECASE)
        if session_match:
            context["session_id"] = session_match.group(1)

        # Extract tool name if present
        tool_match = re.search(r"tool[:\s]*([a-zA-Z_]+)", matched_line, re.IGNORECASE)
        if tool_match:
            context["tool_name"] = tool_match.group(1)

        # Extract error message
        error_match = re.search(r"error[:\s]*(.+?)(?:\s|$)", matched_line, re.IGNORECASE)
        if error_match:
            context["error_message"] = error_match.group(1)

        return context

    def _persist_incident(self, incident: Dict[str, Any]):
        """Persist incident to JSONL file."""
        try:
            with open(self.incidents_file, 'a') as f:
                json.dump(incident, f, default=str)
                f.write('\n')
        except Exception as e:
            logger.error(f"[PATTERN WATCHER] Failed to persist incident: {e}")

    def _send_webhook_alert(self, incident: Dict[str, Any]):
        """Send webhook alert for critical incidents."""
        if not self.webhook_url:
            return

        try:
            payload = {
                "alert_type": "agent_failure_pattern",
                "severity": incident["severity"],
                "pattern": incident["pattern"],
                "description": incident["description"],
                "timestamp": incident["timestamp"],
                "matched_line": incident["matched_line"][:500],  # Truncate for webhook
                "correlation_id": incident.get("correlation_id"),
                "session_id": incident.get("session_id"),
                "context": incident.get("context", {}),
                "environment": os.getenv("ENVIRONMENT", "unknown")
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"[PATTERN WATCHER] Alert sent for {incident['pattern']}")
            else:
                logger.error(f"[PATTERN WATCHER] Alert failed: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"[PATTERN WATCHER] Webhook error: {e}")

    def get_recent_incidents(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get incidents from the last N hours."""
        incidents = []
        cutoff = datetime.now() - timedelta(hours=hours)

        try:
            if self.incidents_file.exists():
                with open(self.incidents_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            incident = json.loads(line)
                            incident_time = datetime.fromisoformat(incident["timestamp"])
                            if incident_time > cutoff:
                                incidents.append(incident)
        except Exception as e:
            logger.error(f"[PATTERN WATCHER] Error reading incidents: {e}")

        return incidents

def main():
    """Main entry point for pattern watcher."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor logs for failure patterns")
    parser.add_argument("--log-file", default="api_server.log", help="Log file to monitor")
    parser.add_argument("--incidents-file", default="telemetry/incidents.jsonl", help="File to store incidents")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    watcher = PatternWatcher(args.log_file, args.incidents_file)

    if args.daemon:
        # Run as daemon
        watcher.start()
    else:
        # Run once and show recent incidents
        recent = watcher.get_recent_incidents()
        print(f"Found {len(recent)} incidents in last 24 hours:")
        for incident in recent[-10:]:  # Show last 10
            print(f"  {incident['timestamp']} {incident['severity']} {incident['pattern']}: {incident['description']}")

if __name__ == "__main__":
    main()
