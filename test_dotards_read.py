#!/usr/bin/env python3
"""Read messages from Dotards group - single test."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import load_config
from src.agent.agent import AutomationAgent
from src.memory import SessionManager

config = load_config()
session_manager = SessionManager(storage_dir="data/sessions")
agent = AutomationAgent(config, session_manager=session_manager)

result = agent.run("Read messages from Dotards group", session_id="test_dotards")
print("\n" + "="*80)
print("RESULT:")
print("="*80)
if isinstance(result, dict):
    print(result.get('message', result))
else:
    print(result)

