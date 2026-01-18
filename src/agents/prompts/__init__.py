"""
Agent prompts for the network troubleshooting system.

This module contains system prompts for the layered subagent architecture:
- L2: Environment Awareness
- L3: Precise Measurement
- L4: Diagnostic Analysis
"""

from .l4_diagnostic_analysis import (
    L4_DIAGNOSTIC_ANALYSIS_PROMPT,
    L4_DIAGNOSTIC_ANALYSIS_PROMPT_COMPACT,
    get_l4_prompt,
)

__all__ = [
    "L4_DIAGNOSTIC_ANALYSIS_PROMPT",
    "L4_DIAGNOSTIC_ANALYSIS_PROMPT_COMPACT",
    "get_l4_prompt",
]
