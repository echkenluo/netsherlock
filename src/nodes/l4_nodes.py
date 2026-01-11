"""
L4 Layer Nodes: Analysis and Report Generation.

This module implements the L4 layer of the diagnostic workflow:
- l4_analyze: Analyze measurement results using latency-analysis methodology
- report: Generate final diagnostic report
"""

from src.state import (
    AnalysisResult,
    DiagnosticState,
    MeasurementResult,
    NetworkScope,
    ProblemType,
    Severity,
)


def execute_l4_analyze(state: DiagnosticState) -> DiagnosticState:
    """
    Analyze measurement results.

    Uses the latency-analysis skill methodology to:
    1. Map measurements to data path segments (A-M)
    2. Calculate derived segments
    3. Perform attribution analysis by layer

    In future versions, this will use Claude with the latency-analysis skill.

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with analysis results
    """
    log = state.get("workflow_log", []).copy()
    results = state.get("measurement_results", [])

    log.append("L4 Analyze: Starting analysis...")

    if not results:
        log.append("L4 Analyze: WARNING - No measurement results to analyze")
        return {
            **state,
            "error_state": "No measurement results available",
            "workflow_log": log,
            "current_layer": 4,
        }

    # Extract metrics from results
    segment_data = _extract_segment_data(results)
    attribution = _calculate_attribution(segment_data)

    # Build analysis result
    analysis = AnalysisResult(
        segment_breakdown=segment_data,
        attribution=attribution,
        total_rtt_us=sum(segment_data.values()),
        key_findings=_identify_key_findings(segment_data, attribution),
        recommendations=_generate_recommendations(segment_data, attribution),
    )

    log.append(f"L4 Analyze: Total RTT = {analysis.total_rtt_us:.1f} us")
    log.append(f"L4 Analyze: Attribution breakdown completed")

    return {
        **state,
        "analysis_result": analysis,
        "workflow_log": log,
        "current_layer": 4,
    }


def _extract_segment_data(results: list[MeasurementResult]) -> dict[str, float]:
    """
    Extract segment data from measurement results.

    Maps tool outputs to data path segments according to
    the latency-analysis skill methodology.

    Segments (from SKILL.md):
    - A: Sender VM Path 1 (kernel to virtio)
    - B: Sender Host ReqInternal (OVS processing)
    - C: Physical network (sender to receiver)
    - D: Receiver Host ReqInternal
    - E: Receiver vhost-to-KVM
    - F: Receiver VM Path 1
    - G: Receiver VM Inter-Path
    - H: Receiver VM Path 2
    - I: Receiver Host RepInternal
    - J: Physical network (receiver to sender)
    - K: Sender Host RepInternal
    - L: Sender vhost-to-KVM
    - M: Sender VM Path 2

    Args:
        results: List of measurement results

    Returns:
        Dictionary mapping segment names to latency values (us)
    """
    # Placeholder segment data
    # In production, this will parse actual tool outputs

    segments = {}

    for result in results:
        if not result.success:
            continue

        data = result.parsed_data

        if result.tool_name == "kernel_icmp_rtt":
            if result.host_ref.startswith("source") or result.host_ref == "source_vm":
                # Sender VM measurements
                segments["A"] = data.get("path1_us", 50.0)
                segments["M"] = data.get("path2_us", 45.0)
            else:
                # Receiver VM measurements
                segments["F"] = data.get("path1_us", 48.0)
                segments["G"] = data.get("inter_path_us", 10.0)
                segments["H"] = data.get("path2_us", 47.0)

        elif result.tool_name == "icmp_drop_detector":
            if result.host_ref.startswith("source") or result.host_ref == "source_host":
                segments["B"] = data.get("req_internal_us", 80.0)
                segments["K"] = data.get("rep_internal_us", 75.0)
            else:
                segments["D"] = data.get("req_internal_us", 82.0)
                segments["I"] = data.get("rep_internal_us", 78.0)

        elif result.tool_name == "tun_tx_to_kvm_irq":
            if result.host_ref.startswith("source") or result.host_ref == "source_host":
                segments["L"] = data.get("total_us", 120.0)
            else:
                segments["E"] = data.get("total_us", 125.0)

    # Calculate physical network (C + J) as derived
    # Formula: External - Receiver_Host_Total (simplified placeholder)
    if "B" in segments and "D" in segments:
        physical_total = 200.0  # Placeholder
        segments["C"] = physical_total / 2
        segments["J"] = physical_total / 2

    return segments


def _calculate_attribution(segments: dict[str, float]) -> dict[str, float]:
    """
    Calculate attribution by layer.

    Layers:
    - VM Internal: A + F + G + H + M
    - Host Internal: B + D + I + K
    - Physical Network: C + J
    - Virtualization: E + L

    Args:
        segments: Segment latency values

    Returns:
        Dictionary mapping layer names to percentages
    """
    total = sum(segments.values())
    if total == 0:
        return {}

    vm_internal = sum(segments.get(s, 0) for s in ["A", "F", "G", "H", "M"])
    host_internal = sum(segments.get(s, 0) for s in ["B", "D", "I", "K"])
    physical = sum(segments.get(s, 0) for s in ["C", "J"])
    virtualization = sum(segments.get(s, 0) for s in ["E", "L"])

    return {
        "VM Internal": round(100 * vm_internal / total, 1),
        "Host Internal": round(100 * host_internal / total, 1),
        "Physical Network": round(100 * physical / total, 1),
        "Virtualization": round(100 * virtualization / total, 1),
    }


def _identify_key_findings(
    segments: dict[str, float], attribution: dict[str, float]
) -> list[str]:
    """
    Identify key findings from the analysis.

    Args:
        segments: Segment latency values
        attribution: Layer attribution percentages

    Returns:
        List of key finding strings
    """
    findings = []

    # Check for dominant layer
    for layer, pct in attribution.items():
        if pct > 40:
            findings.append(f"High attribution to {layer} ({pct}%)")

    # Check for specific segment issues
    if segments.get("E", 0) > 150:
        findings.append("Elevated vhost-to-KVM latency on receiver (E segment)")

    if segments.get("L", 0) > 150:
        findings.append("Elevated vhost-to-KVM latency on sender (L segment)")

    if not findings:
        findings.append("No significant issues detected")

    return findings


def _generate_recommendations(
    segments: dict[str, float], attribution: dict[str, float]
) -> list[str]:
    """
    Generate recommendations based on analysis.

    Args:
        segments: Segment latency values
        attribution: Layer attribution percentages

    Returns:
        List of recommendation strings
    """
    recommendations = []

    if attribution.get("Virtualization", 0) > 30:
        recommendations.append("Check vhost thread CPU pinning and scheduling")

    if attribution.get("Host Internal", 0) > 40:
        recommendations.append("Review OVS flow table size and datapath efficiency")

    if attribution.get("Physical Network", 0) > 30:
        recommendations.append("Check network switch configuration and link status")

    if not recommendations:
        recommendations.append("Continue monitoring - no immediate action required")

    return recommendations


def execute_report(state: DiagnosticState) -> DiagnosticState:
    """
    Generate final diagnostic report.

    Compiles all findings into a structured report.
    Handles both success and error cases.

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with diagnosis report
    """
    log = state.get("workflow_log", []).copy()
    analysis = state.get("analysis_result")
    error = state.get("error_state")

    log.append("Report: Generating final report...")

    # Build report sections
    report_lines = [
        "=" * 60,
        "           NETWORK DIAGNOSTIC REPORT",
        "=" * 60,
        "",
    ]

    # Problem summary
    report_lines.extend([
        "## Problem Summary",
        f"- Type: {state.get('problem_type', 'Unknown')}",
        f"- Scope: {state.get('network_scope', 'Unknown')}",
        f"- Severity: {state.get('severity', 'Unknown')}",
        "",
    ])

    # Error case
    if error:
        report_lines.extend([
            "## Error",
            f"Diagnostic failed: {error}",
            "",
        ])

    # Analysis results
    if analysis:
        report_lines.extend([
            "## Latency Breakdown",
            f"Total RTT: {analysis.total_rtt_us:.1f} us",
            "",
        ])

        if analysis.segment_breakdown:
            report_lines.append("### Segment Details")
            for seg, val in sorted(analysis.segment_breakdown.items()):
                report_lines.append(f"  - {seg}: {val:.1f} us")
            report_lines.append("")

        if analysis.attribution:
            report_lines.append("### Attribution by Layer")
            for layer, pct in analysis.attribution.items():
                bar = "█" * int(pct / 5)
                report_lines.append(f"  - {layer}: {pct}% {bar}")
            report_lines.append("")

        if analysis.key_findings:
            report_lines.append("### Key Findings")
            for finding in analysis.key_findings:
                report_lines.append(f"  • {finding}")
            report_lines.append("")

        if analysis.recommendations:
            report_lines.append("### Recommendations")
            for rec in analysis.recommendations:
                report_lines.append(f"  → {rec}")
            report_lines.append("")

    # Workflow log summary
    report_lines.extend([
        "## Workflow Summary",
        f"Layers completed: L1 → L2 → L3 → L4",
        "",
        "=" * 60,
    ])

    report = "\n".join(report_lines)

    log.append("Report: Generation complete")

    return {
        **state,
        "diagnosis_report": report,
        "workflow_log": log,
        "current_layer": 5,
    }
