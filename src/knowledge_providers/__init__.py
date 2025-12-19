"""
Knowledge Providers Package

This package provides external knowledge sources for factual information retrieval.
Currently supports:
- Wikipedia lookup via REST API
- Caching and error handling for reliability

Future providers could include:
- Wolfram Alpha
- Dictionary APIs
- Academic databases
- News aggregators
"""

from .wiki import lookup_wikipedia
from .models import KnowledgeResult

__all__ = [
    "lookup_wikipedia",
    "KnowledgeResult",
]
