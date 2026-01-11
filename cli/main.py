"""
CLI Entry Point for Network Troubleshooting Agent.

This module provides the command-line interface for the network
troubleshooting agent, allowing users to:
- Run interactive diagnostic sessions
- Execute specific diagnostic types
- View diagnostic reports
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph import create_diagnostic_graph, get_graph_visualization
from src.state import (
    DiagnosticState,
    NetworkScope,
    ProblemType,
    TriggerSource,
    create_initial_state,
)

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Network Troubleshooting Agent - AI-driven network diagnostics."""
    pass


@cli.command()
@click.option(
    "--type",
    "problem_type",
    type=click.Choice(["latency", "packet_drop", "connectivity"]),
    required=True,
    help="Type of problem to diagnose",
)
@click.option(
    "--src-vm",
    "src_vm",
    help="Source VM UUID (for VM network diagnostics)",
)
@click.option(
    "--dst-vm",
    "dst_vm",
    help="Destination VM UUID (for VM network diagnostics)",
)
@click.option(
    "--src-host",
    "src_host",
    help="Source host IP address",
)
@click.option(
    "--dst-host",
    "dst_host",
    help="Destination host IP address",
)
@click.option(
    "--scope",
    type=click.Choice(["vm", "system"]),
    default="vm",
    help="Network scope (vm or system)",
)
def diagnose(
    problem_type: str,
    src_vm: str | None,
    dst_vm: str | None,
    src_host: str | None,
    dst_host: str | None,
    scope: str,
):
    """
    Run a diagnostic workflow for the specified problem type.

    Example:
        network-ops-agent diagnose --type latency --src-vm abc123 --dst-vm def456

    """
    console.print(Panel.fit(
        "[bold blue]Network Troubleshooting Agent[/bold blue]\n"
        f"Problem Type: {problem_type}\n"
        f"Network Scope: {scope}",
        title="Starting Diagnostic",
    ))

    # Build user query from options
    query_parts = [f"Diagnose {problem_type} issue"]
    if scope == "vm":
        query_parts.append("in VM network")
        if src_vm:
            query_parts.append(f"from VM {src_vm}")
        if dst_vm:
            query_parts.append(f"to VM {dst_vm}")
    else:
        query_parts.append("in system network")

    if src_host:
        query_parts.append(f"on host {src_host}")
    if dst_host:
        query_parts.append(f"to host {dst_host}")

    user_query = " ".join(query_parts)

    # Create initial state
    initial_state = create_initial_state(
        trigger_source=TriggerSource.CLI,
        user_query=user_query,
    )

    # Run the diagnostic workflow
    _run_workflow(initial_state)


@cli.command()
def graph():
    """Display the diagnostic workflow graph structure."""
    console.print(Panel(
        get_graph_visualization(),
        title="Diagnostic Workflow Graph (Mermaid)",
        subtitle="Copy to https://mermaid.live to visualize",
    ))


@cli.command()
def interactive():
    """
    Start an interactive diagnostic session.

    Allows step-by-step control of the diagnostic workflow.
    """
    console.print(Panel.fit(
        "[bold green]Interactive Mode[/bold green]\n"
        "Type 'help' for available commands, 'quit' to exit.",
        title="Network Troubleshooting Agent",
    ))

    while True:
        try:
            user_input = console.input("[bold cyan]> [/bold cyan]").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == "help":
                _show_help()
                continue

            if user_input.lower() == "graph":
                console.print(get_graph_visualization())
                continue

            # Treat other input as a diagnostic query
            initial_state = create_initial_state(
                trigger_source=TriggerSource.CLI,
                user_query=user_input,
            )
            _run_workflow(initial_state)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type 'quit' to exit.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def _run_workflow(initial_state: DiagnosticState):
    """
    Execute the diagnostic workflow and display results.

    Args:
        initial_state: Initial state for the workflow
    """
    try:
        # Create the graph
        graph = create_diagnostic_graph()

        # Display progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running diagnostic workflow...", total=None)

            # Execute the graph
            config = {"configurable": {"thread_id": "cli-session"}}
            result = graph.invoke(initial_state, config)

            progress.update(task, description="Complete!")

        # Display results
        _display_results(result)

    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        console.print("[yellow]Run: pip install langgraph langchain-core[/yellow]")
    except Exception as e:
        console.print(f"[red]Workflow error: {e}[/red]")
        raise


def _display_results(state: DiagnosticState):
    """
    Display diagnostic results in a formatted way.

    Args:
        state: Final state from the workflow
    """
    # Show the report if available
    report = state.get("diagnosis_report")
    if report:
        console.print()
        console.print(Panel(report, title="Diagnostic Report", border_style="green"))

    # Show workflow log summary
    log = state.get("workflow_log", [])
    if log:
        table = Table(title="Workflow Log", show_header=False)
        table.add_column("Entry", style="dim")

        for entry in log[-10:]:  # Show last 10 entries
            table.add_row(entry)

        console.print()
        console.print(table)

    # Show error if any
    error = state.get("error_state")
    if error:
        console.print(f"\n[red]Error: {error}[/red]")


def _show_help():
    """Display help information for interactive mode."""
    help_text = """
[bold]Available Commands:[/bold]

  [cyan]help[/cyan]       - Show this help message
  [cyan]graph[/cyan]      - Display the workflow graph
  [cyan]quit[/cyan]       - Exit interactive mode

[bold]Diagnostic Queries:[/bold]

  Just type a natural language query to start a diagnostic:

  [dim]> Diagnose latency between VM abc123 and VM def456[/dim]
  [dim]> Check for packet drops on host 192.168.1.100[/dim]
  [dim]> Analyze connectivity issue in VM network[/dim]
"""
    console.print(Panel(help_text, title="Help", border_style="blue"))


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
