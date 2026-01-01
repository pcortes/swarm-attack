"""Research commands for Open Source Librarian.

Commands for researching external libraries with evidence-backed responses.
This module should NOT import heavy modules at the top level - use lazy imports inside functions.
"""
from __future__ import annotations

from typing import Optional

import typer

from swarm_attack.cli.common import get_config_or_default, get_console

# Create research command group
app = typer.Typer(
    name="research",
    help="Open source library research commands",
    no_args_is_help=False,
)

console = get_console()


@app.callback(invoke_without_command=True)
def research(
    ctx: typer.Context,
    query: Optional[str] = typer.Argument(None, help="Research query"),
    depth: str = typer.Option(
        "medium",
        "--depth",
        "-d",
        help="Research depth: quick, medium, or thorough",
    ),
    library: Optional[str] = typer.Option(
        None,
        "--library",
        "-l",
        help="Focus on a specific library (e.g., 'langchain', 'pydantic')",
    ),
    request_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Override request type classification: conceptual, implementation, context, comprehensive",
    ),
) -> None:
    """
    Research external libraries with evidence-backed responses.

    The Open Source Librarian agent researches libraries and provides
    answers with GitHub permalinks as citations. It never fabricates -
    it admits uncertainty when evidence is insufficient.

    Examples:
        # Basic research query
        swarm-attack research "How do I use pydantic validators?"

        # Quick lookup focused on specific library
        swarm-attack research "retry logic" --library tenacity --depth quick

        # Thorough implementation search
        swarm-attack research "connection pooling" --library httpx --depth thorough --type implementation
    """
    # If no query provided, show help
    if query is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    # Validate depth
    valid_depths = ["quick", "medium", "thorough"]
    if depth not in valid_depths:
        console.print(f"[red]Error:[/red] Invalid depth '{depth}'")
        console.print(f"  Valid options: {', '.join(valid_depths)}")
        raise typer.Exit(1)

    # Validate request_type if provided
    valid_types = ["conceptual", "implementation", "context", "comprehensive"]
    if request_type is not None and request_type not in valid_types:
        console.print(f"[red]Error:[/red] Invalid request type '{request_type}'")
        console.print(f"  Valid options: {', '.join(valid_types)}")
        raise typer.Exit(1)

    # Lazy imports for heavy modules
    from swarm_attack.agents import LibrarianAgent
    from swarm_attack.config import load_config, ConfigError

    # Load config
    try:
        config = load_config()
    except ConfigError:
        config = get_config_or_default()

    # Build context for agent
    context = {
        "query": query,
        "depth": depth,
        "libraries": [library] if library else None,
        "request_type": request_type,
    }

    # Display research parameters
    console.print(f"\n[cyan]Researching:[/cyan] {query}")
    console.print(f"[dim]Depth:[/dim] {depth}")
    if library:
        console.print(f"[dim]Library:[/dim] {library}")
    if request_type:
        console.print(f"[dim]Type:[/dim] {request_type}")
    console.print()

    # Create and run agent
    agent = LibrarianAgent(config)

    with console.status("[yellow]Researching...[/yellow]"):
        result = agent.run(context)

    # Display results
    console.print()

    if result.success:
        console.print("[green]Research Complete[/green]\n")

        # Display answer
        answer = result.output.get("answer", "No answer provided")
        console.print(answer)

        # Display citations
        citations = result.output.get("citations", [])
        if citations:
            console.print("\n[cyan]Citations:[/cyan]")
            for citation in citations:
                url = citation.get("url", "")
                context_text = citation.get("context", "")
                console.print(f"  - {url}")
                if context_text:
                    console.print(f"    [dim]{context_text}[/dim]")

        # Display confidence and cost
        confidence = result.output.get("confidence", 0.0)
        console.print(f"\n[dim]Confidence:[/dim] {confidence:.0%}")
        console.print(f"[dim]Cost:[/dim] ${result.cost_usd:.4f}")
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)
