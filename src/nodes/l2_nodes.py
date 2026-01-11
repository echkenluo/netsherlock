"""
L2 Layer Nodes: Environment Collection and Deployment Decision.

This module implements the L2 layer of the diagnostic workflow:
- l2_collect: Collect environment information using NetworkEnvCollector
- l2_decide: Make deployment decision for measurement tools
"""

from src.state import (
    DeploymentDecision,
    DiagnosticState,
    MeasurementToolConfig,
    NetworkScope,
    ProblemType,
    VMInfo,
    VMNicInfo,
)


def execute_l2_collect(state: DiagnosticState) -> DiagnosticState:
    """
    Collect environment information.

    Uses NetworkEnvCollector (from troubleshooting-tools) to gather:
    - VM info: qemu_pid, vnets, tap_fds, vhost_fds, vhost_pids
    - OVS topology: bridges, ports
    - Network path between source and destination

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with environment information
    """
    log = state.get("workflow_log", []).copy()
    network_scope = state.get("network_scope")

    log.append("L2 Collect: Starting environment collection...")

    # TODO: Integrate with actual NetworkEnvCollector
    # For now, create placeholder data structure

    if network_scope == NetworkScope.VM_NETWORK:
        # Placeholder VM info - will be replaced with actual collection
        source_vm = VMInfo(
            vm_uuid="placeholder-source-uuid",
            qemu_pid=None,
            nics=[
                VMNicInfo(
                    mac="00:00:00:00:00:01",
                    vnet_name="vnet0",
                    ovs_bridge="br-int",
                )
            ],
        )
        dest_vm = VMInfo(
            vm_uuid="placeholder-dest-uuid",
            qemu_pid=None,
            nics=[
                VMNicInfo(
                    mac="00:00:00:00:00:02",
                    vnet_name="vnet1",
                    ovs_bridge="br-int",
                )
            ],
        )

        log.append("L2 Collect: Collected VM network environment (placeholder)")

        return {
            **state,
            "source_vm": source_vm,
            "dest_vm": dest_vm,
            "network_path": [
                "source_vm_kernel",
                "source_virtio",
                "source_vhost",
                "source_ovs",
                "physical_network",
                "dest_ovs",
                "dest_vhost",
                "dest_virtio",
                "dest_vm_kernel",
            ],
            "workflow_log": log,
            "current_layer": 2,
        }

    else:
        # System network - placeholder
        log.append("L2 Collect: System network collection not yet implemented")

        return {
            **state,
            "workflow_log": log,
            "current_layer": 2,
            "error_state": "System network collection not yet implemented",
        }


def execute_l2_decide(state: DiagnosticState) -> DiagnosticState:
    """
    Make deployment decision for measurement tools.

    Based on problem type and collected environment, determines:
    - Which measurement tools to deploy
    - Tool parameters (interfaces, IPs, filters)
    - Classification as receiver or sender tools

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with deployment decision
    """
    log = state.get("workflow_log", []).copy()
    problem_type = state.get("problem_type")
    network_scope = state.get("network_scope")

    log.append("L2 Decide: Making deployment decision...")

    # Base tool path (relative to troubleshooting-tools repo)
    base_path = "/Users/echken/workspace/troubleshooting-tools/measurement-tools"

    receiver_tools = []
    sender_tools = []

    if problem_type == ProblemType.LATENCY and network_scope == NetworkScope.VM_NETWORK:
        # VM latency diagnosis tools
        receiver_tools = [
            MeasurementToolConfig(
                tool_name="kernel_icmp_rtt",
                tool_path=f"{base_path}/performance/kernel_icmp_rtt.py",
                host_ref="dest_vm",
                args={"interface": "eth0"},
                duration=30,
                is_receiver=True,
            ),
            MeasurementToolConfig(
                tool_name="icmp_drop_detector",
                tool_path=f"{base_path}/linux-network-stack/packet-drop/icmp_drop_detector.py",
                host_ref="dest_host",
                args={},
                duration=30,
                is_receiver=True,
            ),
            MeasurementToolConfig(
                tool_name="tun_tx_to_kvm_irq",
                tool_path=f"{base_path}/kvm-virt-network/tun/tun_tx_to_kvm_irq.py",
                host_ref="dest_host",
                args={},
                duration=30,
                is_receiver=True,
            ),
        ]

        sender_tools = [
            MeasurementToolConfig(
                tool_name="kernel_icmp_rtt",
                tool_path=f"{base_path}/performance/kernel_icmp_rtt.py",
                host_ref="source_vm",
                args={"interface": "eth0"},
                duration=30,
                is_receiver=False,
            ),
            MeasurementToolConfig(
                tool_name="icmp_drop_detector",
                tool_path=f"{base_path}/linux-network-stack/packet-drop/icmp_drop_detector.py",
                host_ref="source_host",
                args={},
                duration=30,
                is_receiver=False,
            ),
            MeasurementToolConfig(
                tool_name="tun_tx_to_kvm_irq",
                tool_path=f"{base_path}/kvm-virt-network/tun/tun_tx_to_kvm_irq.py",
                host_ref="source_host",
                args={},
                duration=30,
                is_receiver=False,
            ),
        ]

        decision = DeploymentDecision(
            measurement_type="vm_latency",
            receiver_tools=receiver_tools,
            sender_tools=sender_tools,
            duration=30,
            rationale="Standard VM latency diagnosis: kernel_icmp_rtt for end-to-end RTT, "
            "icmp_drop_detector for host-level drop detection, "
            "tun_tx_to_kvm_irq for vhost-to-KVM latency",
        )

        log.append(
            f"L2 Decide: Selected {len(receiver_tools)} receiver tools, "
            f"{len(sender_tools)} sender tools"
        )
        log.append(f"L2 Decide: Rationale: {decision.rationale}")

    elif problem_type == ProblemType.PACKET_DROP:
        # Packet drop diagnosis - simplified for MVP
        decision = DeploymentDecision(
            measurement_type="packet_drop",
            receiver_tools=[],
            sender_tools=[],
            duration=30,
            rationale="Packet drop diagnosis not yet implemented in MVP",
        )
        log.append("L2 Decide: Packet drop diagnosis not yet implemented")

    else:
        # Default/fallback
        decision = DeploymentDecision(
            measurement_type="unknown",
            receiver_tools=[],
            sender_tools=[],
            duration=30,
            rationale="No specific tools configured for this problem type",
        )
        log.append("L2 Decide: No tools configured for this problem type")

    return {
        **state,
        "deployment_decision": decision,
        "measurement_plan": decision,
        "l2_env_reasoning": decision.rationale,
        "workflow_log": log,
        "current_layer": 2,
    }
