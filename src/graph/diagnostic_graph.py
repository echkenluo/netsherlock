"""
LangGraph Diagnostic Workflow Definition.

This module defines the diagnostic workflow as a LangGraph state machine.
The workflow progresses through 4 layers:
  L1: Monitoring & Classification
  L2: Environment Collection & Deployment Decision
  L3: Measurement Coordination (deterministic)
  L4: Analysis & Report Generation

Key design decisions:
  - LangGraph handles orchestration (fixed layer sequence, conditional routing)
  - Claude Agent SDK handles node execution (AI reasoning within nodes)
  - L3 uses pure Python for deterministic multi-point coordination
"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.state import DiagnosticState, ProblemType


# === Routing Functions ===


def route_after_l1_classify(state: DiagnosticState) -> Literal[
    "l2_collect",
    "l3_prepare",
    "report",
]:
    """
    Route after L1 classification.

    Decision logic:
    - If environment info already exists (from webhook context): skip to L3
    - If problem type couldn't be determined: go to report with error
    - Otherwise: proceed to L2 for environment collection
    """
    # If we have both source and dest info, skip L2
    if state.get("source_vm") and state.get("dest_vm"):
        return "l3_prepare"

    if state.get("source_system") and state.get("dest_system"):
        return "l3_prepare"

    # If classification failed, go to report with error
    if not state.get("problem_type"):
        return "report"

    # Normal flow: proceed to L2
    return "l2_collect"


def route_after_l2_decide(state: DiagnosticState) -> Literal[
    "l3_prepare",
    "l2_collect",
    "report",
]:
    """
    Route after L2 deployment decision.

    Decision logic:
    - If deployment decision is ready: proceed to L3
    - If more info needed: loop back to L2 collection
    - If cannot proceed: go to report with partial findings
    """
    deployment = state.get("deployment_decision")

    if deployment and (deployment.receiver_tools or deployment.sender_tools):
        return "l3_prepare"

    # Check for error state
    if state.get("error_state"):
        return "report"

    # Check retry count
    if state.get("retry_count", 0) >= state.get("max_retries", 3):
        return "report"

    # Need more info
    return "l2_collect"


def route_after_l3_execute(state: DiagnosticState) -> Literal["l4_analyze", "report"]:
    """
    Route after L3 measurement execution.

    Decision logic:
    - If measurements collected successfully: proceed to L4
    - If measurement failed: go to report with error
    """
    results = state.get("measurement_results", [])

    if results and any(r.success for r in results):
        return "l4_analyze"

    return "report"


# === Node Functions (Placeholders - to be implemented) ===


def l1_monitor_node(state: DiagnosticState) -> DiagnosticState:
    """
    L1: Monitor and extract initial context.

    For CLI: Parse user query
    For Webhook: Parse alert payload
    """
    from src.nodes.l1_nodes import execute_l1_monitor

    return execute_l1_monitor(state)


def l1_classify_node(state: DiagnosticState) -> DiagnosticState:
    """
    L1: Classify the problem type and network scope.

    Uses Claude to analyze the context and determine:
    - Problem type (latency, packet_drop, connectivity)
    - Network scope (vm_network, system_network)
    - Severity level
    """
    from src.nodes.l1_nodes import execute_l1_classify

    return execute_l1_classify(state)


def l2_collect_node(state: DiagnosticState) -> DiagnosticState:
    """
    L2: Collect environment information.

    Uses NetworkEnvCollector to gather:
    - VM info (qemu_pid, vnets, vhost_pids)
    - OVS topology
    - Network path
    """
    from src.nodes.l2_nodes import execute_l2_collect

    return execute_l2_collect(state)


def l2_decide_node(state: DiagnosticState) -> DiagnosticState:
    """
    L2: Make deployment decision.

    Uses Claude to determine:
    - Which measurement tools to deploy
    - Tool parameters based on environment
    - Receiver vs sender classification
    """
    from src.nodes.l2_nodes import execute_l2_decide

    return execute_l2_decide(state)


def l3_prepare_node(state: DiagnosticState) -> DiagnosticState:
    """
    L3: Prepare measurement plan.

    Validates the deployment decision and prepares
    the execution order for multi-point measurement.
    """
    from src.nodes.l3_nodes import execute_l3_prepare

    return execute_l3_prepare(state)


def l3_execute_node(state: DiagnosticState) -> DiagnosticState:
    """
    L3: Execute measurements with deterministic coordination.

    CRITICAL: This node is pure Python (not Claude-driven) to ensure:
    1. Receiver tools start BEFORE sender tools
    2. Parallel execution within each phase
    3. Proper result collection
    """
    from src.nodes.l3_nodes import execute_l3_execute

    return execute_l3_execute(state)


def l4_analyze_node(state: DiagnosticState) -> DiagnosticState:
    """
    L4: Analyze measurement results.

    Uses Claude with latency-analysis skill to:
    - Map measurements to data path segments
    - Calculate derived segments
    - Perform attribution analysis
    """
    from src.nodes.l4_nodes import execute_l4_analyze

    return execute_l4_analyze(state)


def report_node(state: DiagnosticState) -> DiagnosticState:
    """
    Generate final diagnostic report.

    Compiles all findings into a structured report.
    Handles both success and error cases.
    """
    from src.nodes.l4_nodes import execute_report

    return execute_report(state)


# === Graph Construction ===


def create_diagnostic_graph() -> StateGraph:
    """
    Create the diagnostic workflow graph.

    Graph structure:
    ```
    [START] -> [l1_monitor] -> [l1_classify]
                                    |
                          +---------+---------+
                          |                   |
                          v                   v
                    [l2_collect]        [l3_prepare] (skip L2)
                          |                   |
                          v                   |
                    [l2_decide]               |
                          |                   |
                          +----> [l3_prepare] <+
                                      |
                                      v
                               [l3_execute]
                                      |
                                      v
                               [l4_analyze]
                                      |
                                      v
                                 [report] -> [END]
    ```

    Returns:
        Compiled StateGraph with memory checkpointer
    """
    # Create the graph
    graph = StateGraph(DiagnosticState)

    # Add nodes
    graph.add_node("l1_monitor", l1_monitor_node)
    graph.add_node("l1_classify", l1_classify_node)
    graph.add_node("l2_collect", l2_collect_node)
    graph.add_node("l2_decide", l2_decide_node)
    graph.add_node("l3_prepare", l3_prepare_node)
    graph.add_node("l3_execute", l3_execute_node)
    graph.add_node("l4_analyze", l4_analyze_node)
    graph.add_node("report", report_node)

    # Fixed edges (mandatory sequence within layers)
    graph.add_edge("l1_monitor", "l1_classify")
    graph.add_edge("l2_collect", "l2_decide")
    graph.add_edge("l3_prepare", "l3_execute")
    graph.add_edge("l4_analyze", "report")
    graph.add_edge("report", END)

    # Conditional edges (AI-driven decisions)
    graph.add_conditional_edges(
        "l1_classify",
        route_after_l1_classify,
        {
            "l2_collect": "l2_collect",
            "l3_prepare": "l3_prepare",
            "report": "report",
        },
    )

    graph.add_conditional_edges(
        "l2_decide",
        route_after_l2_decide,
        {
            "l3_prepare": "l3_prepare",
            "l2_collect": "l2_collect",
            "report": "report",
        },
    )

    graph.add_conditional_edges(
        "l3_execute",
        route_after_l3_execute,
        {
            "l4_analyze": "l4_analyze",
            "report": "report",
        },
    )

    # Set entry point
    graph.set_entry_point("l1_monitor")

    # Compile with memory checkpointer for state persistence
    return graph.compile(checkpointer=MemorySaver())


def get_graph_visualization() -> str:
    """
    Get a Mermaid diagram representation of the graph.

    Returns:
        Mermaid diagram string
    """
    return """
    graph TD
        START((Start)) --> l1_monitor[L1: Monitor]
        l1_monitor --> l1_classify[L1: Classify]

        l1_classify -->|needs env| l2_collect[L2: Collect]
        l1_classify -->|env known| l3_prepare[L3: Prepare]
        l1_classify -->|error| report[Report]

        l2_collect --> l2_decide[L2: Decide]

        l2_decide -->|ready| l3_prepare
        l2_decide -->|need more| l2_collect
        l2_decide -->|cannot proceed| report

        l3_prepare --> l3_execute[L3: Execute]

        l3_execute -->|success| l4_analyze[L4: Analyze]
        l3_execute -->|failed| report

        l4_analyze --> report
        report --> END((End))

        style l3_execute fill:#ff9,stroke:#333
        style l3_prepare fill:#ff9,stroke:#333
    """
