"""
Diagnostic State Schema for LangGraph workflow.

This module defines the state schema used by the LangGraph diagnostic workflow.
The state is passed between nodes and tracks the entire diagnostic process
from alert/input through environment collection, measurement, and analysis.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TypedDict


class ProblemType(str, Enum):
    """Types of network problems that can be diagnosed."""

    LATENCY = "latency"
    PACKET_DROP = "packet_drop"
    CONNECTIVITY = "connectivity"


class NetworkScope(str, Enum):
    """Scope of the network being diagnosed."""

    VM_NETWORK = "vm_network"
    SYSTEM_NETWORK = "system_network"


class Severity(str, Enum):
    """Severity levels for problems."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TriggerSource(str, Enum):
    """Source that triggered the diagnostic workflow."""

    CLI = "cli"
    WEBHOOK = "webhook"
    API = "api"


@dataclass
class VMNicInfo:
    """VM NIC information from environment collection."""

    mac: str
    vnet_name: str
    ovs_bridge: str | None = None
    tap_fds: list[int] = field(default_factory=list)
    vhost_fds: list[int] = field(default_factory=list)
    vhost_pids: list[int] = field(default_factory=list)


@dataclass
class VMInfo:
    """VM information from environment collection."""

    vm_uuid: str
    qemu_pid: int | None = None
    nics: list[VMNicInfo] = field(default_factory=list)
    host_ip: str | None = None


@dataclass
class SystemNetworkInfo:
    """System network information from environment collection."""

    port_name: str
    port_type: str
    ip_address: str | None = None
    ovs_bridge: str | None = None
    physical_nics: list[str] = field(default_factory=list)


@dataclass
class MeasurementToolConfig:
    """Configuration for a measurement tool deployment."""

    tool_name: str
    tool_path: str
    host_ref: str
    args: dict[str, Any] = field(default_factory=dict)
    duration: int = 30
    is_receiver: bool = False


@dataclass
class DeploymentDecision:
    """Tool deployment decision from L2."""

    measurement_type: str
    receiver_tools: list[MeasurementToolConfig] = field(default_factory=list)
    sender_tools: list[MeasurementToolConfig] = field(default_factory=list)
    duration: int = 30
    rationale: str = ""


@dataclass
class MeasurementResult:
    """Result from a measurement tool execution."""

    tool_name: str
    host_ref: str
    success: bool
    output: str | None = None
    parsed_data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class AnalysisResult:
    """Result from L4 analysis."""

    segment_breakdown: dict[str, float] = field(default_factory=dict)
    attribution: dict[str, float] = field(default_factory=dict)
    total_rtt_us: float | None = None
    key_findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class DiagnosticState(TypedDict, total=False):
    """
    LangGraph state schema for the diagnostic workflow.

    This TypedDict defines all the fields that can be passed between
    nodes in the workflow graph. Fields are optional (total=False)
    to allow incremental population as the workflow progresses.
    """

    # === Trigger Context ===
    trigger_source: TriggerSource
    alert_payload: dict[str, Any] | None
    user_query: str | None

    # === L1: Problem Classification ===
    problem_type: ProblemType | None
    network_scope: NetworkScope | None
    severity: Severity | None
    l1_classification_reasoning: str | None

    # === L2: Environment Context ===
    source_vm: VMInfo | None
    dest_vm: VMInfo | None
    source_system: SystemNetworkInfo | None
    dest_system: SystemNetworkInfo | None
    network_path: list[str] | None
    deployment_decision: DeploymentDecision | None
    l2_env_reasoning: str | None

    # === L3: Measurement Coordination ===
    measurement_plan: DeploymentDecision | None
    active_processes: list[dict[str, Any]]
    measurement_results: list[MeasurementResult]
    l3_execution_log: list[str]

    # === L4: Analysis ===
    analysis_result: AnalysisResult | None
    diagnosis_report: str | None

    # === Workflow Control ===
    current_layer: int
    error_state: str | None
    should_retry: bool
    max_retries: int
    retry_count: int
    workflow_log: list[str]


def create_initial_state(
    trigger_source: TriggerSource = TriggerSource.CLI,
    alert_payload: dict[str, Any] | None = None,
    user_query: str | None = None,
) -> DiagnosticState:
    """
    Create an initial diagnostic state with default values.

    Args:
        trigger_source: Where the diagnostic was triggered from
        alert_payload: Optional Grafana alert payload
        user_query: Optional user query string

    Returns:
        A properly initialized DiagnosticState
    """
    return DiagnosticState(
        trigger_source=trigger_source,
        alert_payload=alert_payload,
        user_query=user_query,
        problem_type=None,
        network_scope=None,
        severity=None,
        l1_classification_reasoning=None,
        source_vm=None,
        dest_vm=None,
        source_system=None,
        dest_system=None,
        network_path=None,
        deployment_decision=None,
        l2_env_reasoning=None,
        measurement_plan=None,
        active_processes=[],
        measurement_results=[],
        l3_execution_log=[],
        analysis_result=None,
        diagnosis_report=None,
        current_layer=1,
        error_state=None,
        should_retry=False,
        max_retries=3,
        retry_count=0,
        workflow_log=[],
    )
