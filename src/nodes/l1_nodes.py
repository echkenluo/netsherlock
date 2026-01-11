"""
L1 Layer Nodes: Monitoring and Classification.

This module implements the L1 layer of the diagnostic workflow:
- l1_monitor: Extract initial context from trigger source
- l1_classify: Classify problem type and network scope
"""

from src.state import (
    DiagnosticState,
    NetworkScope,
    ProblemType,
    Severity,
    TriggerSource,
)


def execute_l1_monitor(state: DiagnosticState) -> DiagnosticState:
    """
    Extract initial context from the trigger source.

    For CLI triggers:
    - Parse user query to extract VM/host identifiers
    - Identify problem description

    For Webhook triggers:
    - Parse Grafana alert payload
    - Extract labels (alertname, instance, vm_name, etc.)
    - Extract annotations (summary, description)

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with extracted context
    """
    trigger = state.get("trigger_source", TriggerSource.CLI)
    log = state.get("workflow_log", []).copy()

    if trigger == TriggerSource.WEBHOOK:
        # Parse Grafana webhook payload
        payload = state.get("alert_payload", {})
        alerts = payload.get("alerts", [])

        if alerts:
            alert = alerts[0]
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})

            log.append(
                f"L1 Monitor: Received webhook alert - {labels.get('alertname', 'unknown')}"
            )
            log.append(f"L1 Monitor: Instance: {labels.get('instance', 'unknown')}")
            log.append(f"L1 Monitor: Summary: {annotations.get('summary', 'N/A')}")

            # Store relevant context for classification
            return {
                **state,
                "workflow_log": log,
                "current_layer": 1,
            }

    elif trigger == TriggerSource.CLI:
        # Parse user query
        query = state.get("user_query", "")
        log.append(f"L1 Monitor: Processing CLI query - {query[:100]}...")

        return {
            **state,
            "workflow_log": log,
            "current_layer": 1,
        }

    log.append("L1 Monitor: Unknown trigger source")
    return {
        **state,
        "workflow_log": log,
        "current_layer": 1,
    }


def execute_l1_classify(state: DiagnosticState) -> DiagnosticState:
    """
    Classify the problem type and network scope.

    Uses heuristics and patterns to determine:
    - Problem type: latency, packet_drop, or connectivity
    - Network scope: vm_network or system_network
    - Severity level

    In future versions, this will use Claude for intelligent classification.

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with classification results
    """
    log = state.get("workflow_log", []).copy()
    trigger = state.get("trigger_source", TriggerSource.CLI)

    problem_type = None
    network_scope = None
    severity = Severity.MEDIUM
    reasoning = ""

    if trigger == TriggerSource.WEBHOOK:
        # Classify based on alert name
        payload = state.get("alert_payload", {})
        alerts = payload.get("alerts", [])

        if alerts:
            alert = alerts[0]
            labels = alert.get("labels", {})
            alertname = labels.get("alertname", "")

            # Map alert names to problem types
            if "Latency" in alertname or "RTT" in alertname:
                problem_type = ProblemType.LATENCY
            elif "Drop" in alertname or "Loss" in alertname:
                problem_type = ProblemType.PACKET_DROP
            else:
                problem_type = ProblemType.CONNECTIVITY

            # Determine network scope
            if "VM" in alertname or "Vnet" in alertname or labels.get("vm_name"):
                network_scope = NetworkScope.VM_NETWORK
            else:
                network_scope = NetworkScope.SYSTEM_NETWORK

            # Map severity
            sev_label = labels.get("severity", "warning")
            severity = {
                "critical": Severity.CRITICAL,
                "high": Severity.HIGH,
                "warning": Severity.MEDIUM,
                "info": Severity.LOW,
            }.get(sev_label, Severity.MEDIUM)

            reasoning = f"Classified from webhook alert: {alertname}"

    elif trigger == TriggerSource.CLI:
        # Classify based on user query
        query = (state.get("user_query") or "").lower()

        if "latency" in query or "delay" in query or "rtt" in query or "延迟" in query:
            problem_type = ProblemType.LATENCY
        elif "drop" in query or "loss" in query or "丢包" in query:
            problem_type = ProblemType.PACKET_DROP
        else:
            problem_type = ProblemType.CONNECTIVITY

        if "vm" in query or "虚拟机" in query:
            network_scope = NetworkScope.VM_NETWORK
        else:
            network_scope = NetworkScope.SYSTEM_NETWORK

        reasoning = f"Classified from CLI query keywords"

    log.append(f"L1 Classify: Problem type = {problem_type}")
    log.append(f"L1 Classify: Network scope = {network_scope}")
    log.append(f"L1 Classify: Severity = {severity}")

    return {
        **state,
        "problem_type": problem_type,
        "network_scope": network_scope,
        "severity": severity,
        "l1_classification_reasoning": reasoning,
        "workflow_log": log,
        "current_layer": 1,
    }
