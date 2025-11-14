#!/usr/bin/env python3
"""
Trajectory analyzer script for viewing and analyzing LLM orchestration trajectories.

Usage:
    python scripts/analyze_trajectories.py --session-id <session_id>
    python scripts/analyze_trajectories.py --decision-type model_selection
    python scripts/analyze_trajectories.py --stats
    python scripts/analyze_trajectories.py --list-sessions
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.trajectory_query import TrajectoryQuery


def format_trajectory(traj: dict) -> str:
    """Format a trajectory entry for display."""
    lines = []
    lines.append(f"Timestamp: {traj.get('timestamp', 'N/A')}")
    lines.append(f"Session: {traj.get('session_id', 'N/A')}")
    lines.append(f"Phase: {traj.get('phase', 'N/A')}")
    lines.append(f"Component: {traj.get('component', 'N/A')}")
    lines.append(f"Decision Type: {traj.get('decision_type', 'N/A')}")
    
    if traj.get('model_used'):
        lines.append(f"Model: {traj['model_used']}")
    
    if traj.get('reasoning'):
        lines.append(f"Reasoning: {traj['reasoning'][:200]}...")
    
    if traj.get('confidence') is not None:
        lines.append(f"Confidence: {traj['confidence']:.2f}")
    
    if traj.get('tokens_used'):
        tokens = traj['tokens_used']
        if isinstance(tokens, dict):
            lines.append(f"Tokens: {tokens.get('total', 0)} (prompt: {tokens.get('prompt', 0)}, completion: {tokens.get('completion', 0)})")
    
    if traj.get('latency_ms') is not None:
        lines.append(f"Latency: {traj['latency_ms']:.2f}ms")
    
    lines.append(f"Success: {traj.get('success', False)}")
    
    if traj.get('error'):
        lines.append(f"Error: {json.dumps(traj['error'], indent=2)}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze LLM orchestration trajectories")
    parser.add_argument("--session-id", help="Session ID to query")
    parser.add_argument("--decision-type", help="Decision type to filter")
    parser.add_argument("--model", help="Model to filter")
    parser.add_argument("--phase", help="Phase to filter (planning|execution|synthesis|error)")
    parser.add_argument("--component", help="Component to filter (planner|executor|agent|tool)")
    parser.add_argument("--success-only", action="store_true", help="Only show successful trajectories")
    parser.add_argument("--failed-only", action="store_true", help="Only show failed trajectories")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--list-sessions", action="store_true", help="List all sessions")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--limit", type=int, default=100, help="Limit number of results")
    
    args = parser.parse_args()
    
    query = TrajectoryQuery()
    
    if args.list_sessions:
        sessions = query.list_sessions()
        if args.json:
            print(json.dumps(sessions, indent=2))
        else:
            print(f"Found {len(sessions)} sessions:")
            for session in sessions:
                print(f"  - {session.get('session_id')} ({session.get('created_at')})")
        return
    
    if args.stats:
        stats = query.get_statistics(session_id=args.session_id)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("Statistics:")
            print(f"  Total trajectories: {stats['total']}")
            print(f"  Success rate: {stats['success_rate']:.2%}")
            print(f"  Average confidence: {stats['avg_confidence']:.2f}")
            print(f"  Total tokens: {stats['total_tokens']:,}")
            print("\nBy Phase:")
            for phase, count in stats['by_phase'].items():
                print(f"  {phase}: {count}")
            print("\nBy Component:")
            for component, count in stats['by_component'].items():
                print(f"  {component}: {count}")
            print("\nBy Decision Type:")
            for decision_type, count in stats['by_decision_type'].items():
                print(f"  {decision_type}: {count}")
            print("\nBy Model:")
            for model, count in stats['by_model'].items():
                print(f"  {model}: {count}")
        return
    
    # Query trajectories
    if args.session_id:
        trajectories = query.query_by_session(
            args.session_id,
            decision_type=args.decision_type,
            phase=args.phase,
            component=args.component,
            success=True if args.success_only else (False if args.failed_only else None)
        )
    elif args.decision_type:
        trajectories = query.query_by_decision_type(args.decision_type)
    elif args.model:
        trajectories = query.query_by_model(args.model)
    else:
        print("Error: Must specify --session-id, --decision-type, or --model")
        return
    
    # Apply filters
    if args.phase:
        trajectories = [t for t in trajectories if t.get('phase') == args.phase]
    if args.component:
        trajectories = [t for t in trajectories if t.get('component') == args.component]
    if args.success_only:
        trajectories = [t for t in trajectories if t.get('success', False)]
    if args.failed_only:
        trajectories = [t for t in trajectories if not t.get('success', True)]
    
    # Limit results
    trajectories = trajectories[:args.limit]
    
    if args.json:
        print(json.dumps(trajectories, indent=2))
    else:
        print(f"Found {len(trajectories)} trajectories:\n")
        for i, traj in enumerate(trajectories, 1):
            print(f"--- Trajectory {i} ---")
            print(format_trajectory(traj))
            print()


if __name__ == "__main__":
    main()

