"""
Network troubleshooting agents built with Claude Agent SDK.

This module implements a four-layer diagnostic architecture:
- Main Agent: Orchestrates the diagnostic workflow
- L2 Subagent: Environment awareness and topology collection
- L3 Subagent: Precise measurement execution (BCC/eBPF tools)
- L4 Subagent: Diagnostic analysis and report generation
"""

from .prompts import (
    L4_DIAGNOSTIC_ANALYSIS_PROMPT,
    get_l4_prompt,
)

__all__ = [
    "L4_DIAGNOSTIC_ANALYSIS_PROMPT",
    "get_l4_prompt",
]
