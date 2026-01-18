"""
Base agent definitions and common utilities for the network troubleshooting system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProblemType(Enum):
    """Types of network problems the agent can diagnose."""

    VM_NETWORK_LATENCY = "vm_network_latency"
    VM_NETWORK_DROP = "vm_network_drop"
    SYSTEM_NETWORK_LATENCY = "system_network_latency"
    SYSTEM_NETWORK_DROP = "system_network_drop"
    VHOST_OVERLOAD = "vhost_overload"
    OVS_SLOW_PATH = "ovs_slow_path"
    THROUGHPUT_DEGRADATION = "throughput_degradation"
    TCP_RETRANSMISSION = "tcp_retransmission"


class RootCauseCategory(Enum):
    """Categories of root causes identified by L4 analysis."""

    VM_INTERNAL = "vm_internal"  # Guest VM issues
    VHOST_PROCESSING = "vhost_processing"  # vhost-net delays
    HOST_INTERNAL = "host_internal"  # Host networking (OVS, kernel)
    PHYSICAL_NETWORK = "physical_network"  # Physical infrastructure


@dataclass
class AlertContext:
    """Context extracted from an incoming alert."""

    alertname: str
    instance: str
    severity: str = "warning"
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    @property
    def node_ip(self) -> str:
        """Extract node IP from instance label."""
        return self.instance.split(":")[0] if self.instance else ""

    @property
    def problem_type(self) -> ProblemType | None:
        """Map alertname to problem type."""
        mapping = {
            "VMNetworkLatency": ProblemType.VM_NETWORK_LATENCY,
            "VMNetworkDrop": ProblemType.VM_NETWORK_DROP,
            "HostNetworkHighLatency": ProblemType.SYSTEM_NETWORK_LATENCY,
            "HostNetworkLoss": ProblemType.SYSTEM_NETWORK_DROP,
            "VhostCPUHigh": ProblemType.VHOST_OVERLOAD,
            "OVSUpcallHigh": ProblemType.OVS_SLOW_PATH,
        }
        return mapping.get(self.alertname)


@dataclass
class VMInfo:
    """VM information collected by L2."""

    uuid: str
    name: str
    qemu_pid: int
    vhost_tids: list[int]
    vcpu_count: int = 0
    memory_mb: int = 0


@dataclass
class NetworkInfo:
    """Network topology information collected by L2."""

    vnet: str = ""
    mac: str = ""
    ovs_bridge: str = ""
    ovs_port: str = ""
    ofport: int = 0
    phy_nic: str = ""
    bond_members: list[str] = field(default_factory=list)
    ip_address: str = ""
    mtu: int = 1500


@dataclass
class NodeEnvironment:
    """Environment information for a single node."""

    node_ip: str
    hostname: str = ""
    vm: VMInfo | None = None
    network: NetworkInfo = field(default_factory=NetworkInfo)
    ssh_user: str = "root"
    ssh_key_path: str = ""


@dataclass
class NetworkPath:
    """Network path between source and destination."""

    path_type: str  # "vm_to_vm", "system_to_system", "vm_to_system"
    same_host: bool
    segments: list[dict[str, str]]
    tunnel_type: str = "none"  # "vxlan", "gre", "none"


@dataclass
class FlowInfo:
    """Flow characteristics for measurement."""

    src_ip: str
    dst_ip: str
    protocol: str = "icmp"
    src_port: int = 0
    dst_port: int = 0


@dataclass
class NetworkEnvironment:
    """Complete network environment for measurements (L2 output)."""

    problem_type: ProblemType
    measurement_type: str
    source: NodeEnvironment
    destination: NodeEnvironment | None = None
    path: NetworkPath | None = None
    flow: FlowInfo | None = None


@dataclass
class LatencyHistogram:
    """Latency histogram statistics."""

    p50_us: float
    p95_us: float
    p99_us: float
    max_us: float
    samples: int = 0


@dataclass
class LatencySegment:
    """A single latency segment measurement."""

    name: str
    layer: str  # "vm_internal", "vhost_processing", "host_internal", "physical_network"
    description: str = ""
    histogram: LatencyHistogram | None = None


@dataclass
class MeasurementResult:
    """Measurement results from L3."""

    measurement_id: str
    measurement_type: str
    timestamp: str
    duration_seconds: float
    sample_count: int
    segments: list[LatencySegment]
    total_latency: LatencyHistogram | None = None
    environment_summary: dict[str, Any] = field(default_factory=dict)
    raw_data_path: str = ""


@dataclass
class RootCause:
    """Root cause determination from L4."""

    category: RootCauseCategory
    component: str
    confidence: int  # 0-100
    evidence: list[str]
    contributing_factors: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """Action recommendation from L4."""

    priority: int
    action: str
    command: str = ""
    metric: str = ""


@dataclass
class DiagnosisResult:
    """Complete diagnosis result."""

    diagnosis_id: str
    timestamp: str
    alert_source: AlertContext | None
    summary: str
    root_cause: RootCause
    recommendations: list[Recommendation]
    follow_up: dict[str, str] = field(default_factory=dict)
    l1_observations: dict[str, Any] = field(default_factory=dict)
    l2_environment: NetworkEnvironment | None = None
    l3_measurements: MeasurementResult | None = None
