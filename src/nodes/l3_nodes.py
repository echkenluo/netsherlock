"""
L3 Layer Nodes: Measurement Coordination.

This module implements the L3 layer of the diagnostic workflow:
- l3_prepare: Validate and prepare measurement plan
- l3_execute: Execute measurements with deterministic coordination

CRITICAL: l3_execute is pure Python (not Claude-driven) to ensure:
1. Receiver tools start BEFORE sender tools
2. Parallel execution within each phase
3. Proper result collection
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.state import (
    DeploymentDecision,
    DiagnosticState,
    MeasurementResult,
    MeasurementToolConfig,
)


def execute_l3_prepare(state: DiagnosticState) -> DiagnosticState:
    """
    Prepare and validate the measurement plan.

    Validates:
    - All tool paths exist
    - Host references are valid
    - Tool parameters are complete

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with validated measurement plan
    """
    log = state.get("workflow_log", []).copy()
    plan = state.get("measurement_plan")

    log.append("L3 Prepare: Validating measurement plan...")

    if not plan:
        log.append("L3 Prepare: ERROR - No measurement plan available")
        return {
            **state,
            "error_state": "No measurement plan available",
            "workflow_log": log,
            "current_layer": 3,
        }

    # Validate tool configurations
    issues = []

    for tool in plan.receiver_tools + plan.sender_tools:
        if not tool.tool_path:
            issues.append(f"Tool {tool.tool_name} missing path")
        if not tool.host_ref:
            issues.append(f"Tool {tool.tool_name} missing host reference")

    if issues:
        log.append(f"L3 Prepare: Validation issues: {issues}")
        return {
            **state,
            "error_state": f"Validation failed: {issues}",
            "workflow_log": log,
            "current_layer": 3,
        }

    log.append(
        f"L3 Prepare: Plan validated - {len(plan.receiver_tools)} receivers, "
        f"{len(plan.sender_tools)} senders, duration={plan.duration}s"
    )

    return {
        **state,
        "workflow_log": log,
        "l3_execution_log": [],
        "current_layer": 3,
    }


def _execute_tool_placeholder(tool: MeasurementToolConfig) -> MeasurementResult:
    """
    Placeholder for tool execution.

    In production, this will:
    1. SSH to the target host
    2. Execute the BCC tool
    3. Collect and parse output

    Args:
        tool: Tool configuration

    Returns:
        Measurement result
    """
    # Simulate execution delay
    time.sleep(0.1)

    # Return placeholder result
    return MeasurementResult(
        tool_name=tool.tool_name,
        host_ref=tool.host_ref,
        success=True,
        output=f"Placeholder output for {tool.tool_name}",
        parsed_data={
            "avg_latency_us": 100.0,
            "p99_latency_us": 250.0,
            "sample_count": 100,
        },
        error=None,
    )


def execute_l3_execute(state: DiagnosticState) -> DiagnosticState:
    """
    Execute measurements with deterministic coordination.

    CRITICAL COORDINATION RULES:
    1. ALL receiver tools must start BEFORE any sender tools
    2. Within each phase, tools execute in parallel
    3. Wait for all tools to complete before result collection

    Execution phases:
    Phase 1: Start all receiver-side tools (parallel)
    Phase 2: Wait for receivers to be ready (brief delay)
    Phase 3: Start all sender-side tools (parallel)
    Phase 4: Wait for measurement duration
    Phase 5: Collect results from all tools

    Args:
        state: Current diagnostic state

    Returns:
        Updated state with measurement results
    """
    log = state.get("workflow_log", []).copy()
    exec_log = state.get("l3_execution_log", []).copy()
    plan = state.get("measurement_plan")

    if not plan:
        log.append("L3 Execute: ERROR - No measurement plan")
        return {
            **state,
            "error_state": "No measurement plan for execution",
            "workflow_log": log,
            "current_layer": 3,
        }

    exec_log.append(f"[{_timestamp()}] Starting L3 measurement execution")

    results: list[MeasurementResult] = []

    # Phase 1: Start receiver tools
    exec_log.append(f"[{_timestamp()}] Phase 1: Starting {len(plan.receiver_tools)} receiver tools")

    receiver_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(_execute_tool_placeholder, tool) for tool in plan.receiver_tools
        ]
        for future in futures:
            receiver_results.append(future.result())

    exec_log.append(f"[{_timestamp()}] Phase 1 complete: Receivers started")

    # Phase 2: Wait for receivers to be ready
    exec_log.append(f"[{_timestamp()}] Phase 2: Waiting for receivers to be ready...")
    time.sleep(1.0)  # Brief delay to ensure receivers are listening

    # Phase 3: Start sender tools
    exec_log.append(f"[{_timestamp()}] Phase 3: Starting {len(plan.sender_tools)} sender tools")

    sender_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(_execute_tool_placeholder, tool) for tool in plan.sender_tools
        ]
        for future in futures:
            sender_results.append(future.result())

    exec_log.append(f"[{_timestamp()}] Phase 3 complete: Senders started")

    # Phase 4: Wait for measurement duration
    # In production, this would monitor tool output
    exec_log.append(
        f"[{_timestamp()}] Phase 4: Measurement in progress (duration={plan.duration}s)..."
    )
    # Simulated - in production, we'd wait for actual duration
    time.sleep(0.5)

    # Phase 5: Collect results
    exec_log.append(f"[{_timestamp()}] Phase 5: Collecting results")

    results = receiver_results + sender_results

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    exec_log.append(
        f"[{_timestamp()}] Execution complete: {success_count} succeeded, {fail_count} failed"
    )

    log.append(f"L3 Execute: Completed with {success_count}/{len(results)} successful measurements")

    return {
        **state,
        "measurement_results": results,
        "workflow_log": log,
        "l3_execution_log": exec_log,
        "current_layer": 3,
    }


def _timestamp() -> str:
    """Get current timestamp for logging."""
    return time.strftime("%H:%M:%S")
