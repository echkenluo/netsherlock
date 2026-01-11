"""State module for diagnostic workflow."""

from .diagnostic_state import (
    AnalysisResult,
    DeploymentDecision,
    DiagnosticState,
    MeasurementResult,
    MeasurementToolConfig,
    NetworkScope,
    ProblemType,
    Severity,
    SystemNetworkInfo,
    TriggerSource,
    VMInfo,
    VMNicInfo,
    create_initial_state,
)

__all__ = [
    "AnalysisResult",
    "DeploymentDecision",
    "DiagnosticState",
    "MeasurementResult",
    "MeasurementToolConfig",
    "NetworkScope",
    "ProblemType",
    "Severity",
    "SystemNetworkInfo",
    "TriggerSource",
    "VMInfo",
    "VMNicInfo",
    "create_initial_state",
]
