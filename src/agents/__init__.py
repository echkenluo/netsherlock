"""
Network troubleshooting agents built with Claude Agent SDK.

This module implements a four-layer diagnostic architecture:
- Main Agent: Orchestrates the diagnostic workflow
- L2 Subagent: Environment awareness and topology collection
- L3 Subagent: Precise measurement execution (BCC/eBPF tools)
- L4 Subagent: Diagnostic analysis and report generation
"""

from .prompts import (
    MAIN_ORCHESTRATOR_PROMPT,
    L2_ENVIRONMENT_AWARENESS_PROMPT,
    L3_PRECISE_MEASUREMENT_PROMPT,
    L4_DIAGNOSTIC_ANALYSIS_PROMPT,
    get_main_prompt,
    get_l2_prompt,
    get_l3_prompt,
    get_l4_prompt,
)
from .base import (
    ProblemType,
    RootCauseCategory,
    AlertContext,
    VMInfo,
    NetworkInfo,
    NodeEnvironment,
    NetworkPath,
    FlowInfo,
    NetworkEnvironment,
    LatencyHistogram,
    LatencySegment,
    MeasurementResult,
    RootCause,
    Recommendation,
    DiagnosisResult,
)
from .subagents import (
    L2EnvironmentSubagent,
    L3MeasurementSubagent,
    L4AnalysisSubagent,
    create_subagent,
)
from .orchestrator import (
    NetworkTroubleshootingOrchestrator,
    create_orchestrator,
)

__all__ = [
    # Prompts
    "MAIN_ORCHESTRATOR_PROMPT",
    "L2_ENVIRONMENT_AWARENESS_PROMPT",
    "L3_PRECISE_MEASUREMENT_PROMPT",
    "L4_DIAGNOSTIC_ANALYSIS_PROMPT",
    "get_main_prompt",
    "get_l2_prompt",
    "get_l3_prompt",
    "get_l4_prompt",
    # Data types
    "ProblemType",
    "RootCauseCategory",
    "AlertContext",
    "VMInfo",
    "NetworkInfo",
    "NodeEnvironment",
    "NetworkPath",
    "FlowInfo",
    "NetworkEnvironment",
    "LatencyHistogram",
    "LatencySegment",
    "MeasurementResult",
    "RootCause",
    "Recommendation",
    "DiagnosisResult",
    # Subagents
    "L2EnvironmentSubagent",
    "L3MeasurementSubagent",
    "L4AnalysisSubagent",
    "create_subagent",
    # Orchestrator
    "NetworkTroubleshootingOrchestrator",
    "create_orchestrator",
]
