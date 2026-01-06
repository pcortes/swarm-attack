"""Memory store management commands.

Commands for viewing, listing, and pruning memory entries.
This module should NOT import heavy modules at the top level - use lazy imports inside functions.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from swarm_attack.cli.common import get_console

# Create memory command group
memory_app = typer.Typer(
    name="memory",
    help="Memory store management commands",
    no_args_is_help=True,
)

console = get_console()


@memory_app.command("stats")
def stats_command() -> None:
    """
    Show memory store statistics.

    Displays:
    - Total number of entries
    - Entries by category breakdown
    - Total queries performed
    - Average hit count per entry

    Example:
        swarm-attack memory stats
    """
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    stats = store.get_stats()

    # Build stats display
    total_entries = stats.get("total_entries", 0)
    total_queries = stats.get("total_queries", 0)
    avg_hit_count = stats.get("avg_hit_count", 0.0)
    entries_by_category = stats.get("entries_by_category", {})

    info_lines = [
        f"[bold]Total Entries:[/bold] {total_entries}",
        f"[bold]Total Queries:[/bold] {total_queries}",
        f"[bold]Avg Hit Count:[/bold] {avg_hit_count:.2f}",
    ]

    if entries_by_category:
        info_lines.append("")
        info_lines.append("[bold]Entries by Category:[/bold]")
        for category, count in sorted(entries_by_category.items()):
            info_lines.append(f"  {category}: {count}")

    console.print(
        Panel(
            "\n".join(info_lines),
            title="Memory Store Statistics",
            border_style="cyan",
        )
    )


@memory_app.command("list")
def list_command(
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (e.g., checkpoint_decision, schema_drift)",
    ),
    feature_id: Optional[str] = typer.Option(
        None,
        "--feature",
        "-f",
        help="Filter by feature ID",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Maximum number of entries to show",
    ),
) -> None:
    """
    List memory entries with optional filtering.

    Displays memory entries in a table format with ID, category,
    feature, outcome, and creation date.

    Example:
        swarm-attack memory list
        swarm-attack memory list --category schema_drift
        swarm-attack memory list --feature my-feature --limit 10
    """
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    entries = store.query(category=category, feature_id=feature_id, limit=limit)

    if not entries:
        filter_msg = ""
        if category:
            filter_msg += f" category='{category}'"
        if feature_id:
            filter_msg += f" feature='{feature_id}'"

        console.print(
            Panel(
                f"[dim]No memory entries found{' matching' + filter_msg if filter_msg else ''}.[/dim]",
                title="Memory Entries",
                border_style="dim",
            )
        )
        return

    # Create table
    table = Table(title="Memory Entries")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Category", style="cyan")
    table.add_column("Feature", style="green")
    table.add_column("Outcome", style="yellow")
    table.add_column("Created", style="dim")
    table.add_column("Tags", style="magenta", max_width=30)

    for entry in entries:
        # Format the created_at timestamp
        try:
            created = entry.created_at[:19].replace("T", " ")
        except (TypeError, IndexError):
            created = str(entry.created_at)[:19]

        # Format tags
        tags_str = ", ".join(entry.tags[:3])
        if len(entry.tags) > 3:
            tags_str += f" +{len(entry.tags) - 3}"

        table.add_row(
            entry.id[:12],
            entry.category,
            entry.feature_id,
            entry.outcome or "-",
            created,
            tags_str or "-",
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(entries)} entries[/dim]")


@memory_app.command("prune")
def prune_command(
    older_than: int = typer.Option(
        ...,
        "--older-than",
        "-d",
        help="Remove entries older than this many days (required)",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Only prune entries from this category",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be pruned without actually deleting",
    ),
) -> None:
    """
    Prune old entries from memory.

    Removes memory entries older than the specified number of days.
    Use --dry-run to preview what would be deleted.

    Example:
        swarm-attack memory prune --older-than 30
        swarm-attack memory prune --older-than 60 --category checkpoint_decision
        swarm-attack memory prune --older-than 30 --dry-run
    """
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=older_than)
    cutoff_iso = cutoff_date.isoformat()

    # Find entries to prune
    entries_to_prune = []
    all_entries = store.query(category=category, limit=10000)

    for entry in all_entries:
        try:
            if entry.created_at < cutoff_iso:
                entries_to_prune.append(entry)
        except (TypeError, ValueError):
            # Skip entries with invalid dates
            continue

    if not entries_to_prune:
        console.print(
            f"[green]No entries older than {older_than} days found.[/green]"
        )
        return

    if dry_run:
        console.print(f"[yellow]DRY RUN - Would prune {len(entries_to_prune)} entries:[/yellow]\n")

        table = Table(title="Entries to Prune")
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Category", style="cyan")
        table.add_column("Feature", style="green")
        table.add_column("Created", style="dim")

        for entry in entries_to_prune[:20]:
            try:
                created = entry.created_at[:19].replace("T", " ")
            except (TypeError, IndexError):
                created = str(entry.created_at)[:19]

            table.add_row(
                entry.id[:12],
                entry.category,
                entry.feature_id,
                created,
            )

        if len(entries_to_prune) > 20:
            console.print(f"[dim]...and {len(entries_to_prune) - 20} more[/dim]")

        console.print(table)
        console.print(f"\n[yellow]Run without --dry-run to delete these entries.[/yellow]")
        return

    # Actually delete entries
    deleted_count = 0
    for entry in entries_to_prune:
        if store.delete(entry.id):
            deleted_count += 1

    # Save changes
    store.save()

    console.print(
        f"[green]Pruned {deleted_count} entries older than {older_than} days.[/green]"
    )


@memory_app.command("save")
def save_command(
    path: Path = typer.Argument(..., help="Path to save memory file")
) -> None:
    """Save memory to file."""
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    store.save_to_file(path)

    console.print(
        Panel(
            f"[green]Memory saved to {path}[/green]",
            title="Memory Save",
            border_style="green",
        )
    )


@memory_app.command("load")
def load_command(
    path: Path = typer.Argument(..., help="Path to load memory from")
) -> None:
    """Load memory from file."""
    from swarm_attack.memory.store import MemoryStore

    if not path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        raise typer.Exit(1)

    store = MemoryStore.load()
    store.load_from_file(path)
    store.save()

    entries_count = len(store._entries)
    console.print(
        Panel(
            f"[green]Loaded {entries_count} entries from {path}[/green]",
            title="Memory Load",
            border_style="green",
        )
    )


@memory_app.command("export")
def export_command(
    path: Path = typer.Argument(..., help="Path to export to"),
    format: str = typer.Option("json", "--format", "-f", help="Output format (json or yaml)"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category")
) -> None:
    """Export memory to file."""
    from swarm_attack.memory.export import MemoryExporter
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    exporter = MemoryExporter()

    categories = [category] if category else None

    if format.lower() == "yaml":
        exporter.export_yaml(store, path, categories=categories)
    else:
        exporter.export_json(store, path, categories=categories)

    console.print(
        Panel(
            f"[green]Memory exported to {path} ({format})[/green]",
            title="Memory Export",
            border_style="green",
        )
    )


@memory_app.command("import")
def import_command(
    path: Path = typer.Argument(..., help="Path to import from"),
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing or replace")
) -> None:
    """Import memory from file."""
    from swarm_attack.memory.export import MemoryExporter
    from swarm_attack.memory.store import MemoryStore

    if not path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        raise typer.Exit(1)

    store = MemoryStore.load()
    exporter = MemoryExporter()

    count = exporter.import_json(store, path, merge=merge)
    store.save()

    action = "merged" if merge else "replaced"
    console.print(
        Panel(
            f"[green]Imported {count} entries ({action})[/green]",
            title="Memory Import",
            border_style="green",
        )
    )


@memory_app.command("compress")
def compress_command(
    threshold: float = typer.Option(0.8, "--threshold", "-t", help="Similarity threshold")
) -> None:
    """Compress similar memory entries."""
    from swarm_attack.memory.compression import MemoryCompressor
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    compressor = MemoryCompressor()

    original_count = len(store._entries)
    entries = list(store._entries.values())
    compressed = compressor.compress(entries, similarity_threshold=threshold)

    # Clear and re-add compressed entries
    store.clear()
    for entry in compressed:
        store.add(entry)
    store.save()

    new_count = len(store._entries)
    reduced = original_count - new_count

    console.print(
        Panel(
            f"[green]Compressed {original_count} entries to {new_count} ({reduced} reduced)[/green]",
            title="Memory Compression",
            border_style="green",
        )
    )


@memory_app.command("analytics")
def analytics_command() -> None:
    """Show memory analytics report."""
    from swarm_attack.memory.analytics import MemoryAnalytics
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    analytics = MemoryAnalytics(store)

    report = analytics.generate_report()

    console.print(
        Panel(
            report,
            title="Memory Analytics",
            border_style="cyan",
        )
    )


@memory_app.command("patterns")
def patterns_command(
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (e.g., schema_drift, test_failure)",
    ),
    min_occurrences: int = typer.Option(
        3,
        "--min-occurrences",
        "-m",
        help="Minimum pattern occurrences to display",
    ),
) -> None:
    """
    Show detected patterns in memory.

    Displays recurring patterns from memory entries including:
    - Schema drift patterns (classes that repeatedly drift)
    - Fix patterns (fixes that are commonly applied)
    - Failure clusters (tests that fail together)

    Example:
        swarm-attack memory patterns
        swarm-attack memory patterns --category schema_drift
        swarm-attack memory patterns --min-occurrences 5
    """
    from swarm_attack.memory.patterns import PatternDetector
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    detector = PatternDetector(store)

    # Create table for results
    table = Table(title="Detected Patterns")
    table.add_column("Type", style="cyan")
    table.add_column("Name/Target", style="green")
    table.add_column("Occurrences", style="yellow")
    table.add_column("Confidence", style="magenta")

    pattern_count = 0

    # Detect schema drift patterns
    if category is None or category == "schema_drift":
        drift_patterns = detector.detect_recurring_schema_drift(
            min_occurrences=min_occurrences
        )
        for pattern in drift_patterns:
            table.add_row(
                "Schema Drift",
                pattern.class_name,
                str(pattern.occurrence_count),
                f"{pattern.confidence_score:.2f}",
            )
            pattern_count += 1

    # Detect fix patterns
    if category is None or category == "fix_applied":
        fix_patterns = detector.detect_common_fix_patterns(
            min_occurrences=min_occurrences
        )
        for pattern in fix_patterns:
            table.add_row(
                "Fix Pattern",
                pattern.fix_type,
                str(pattern.occurrence_count),
                f"{pattern.confidence_score:.2f}",
            )
            pattern_count += 1

    # Detect failure clusters
    if category is None or category == "test_failure":
        failure_clusters = detector.detect_failure_clusters(
            min_failures=min_occurrences
        )
        for cluster in failure_clusters:
            table.add_row(
                "Failure Cluster",
                cluster.test_path,
                str(cluster.failure_count),
                "-",
            )
            pattern_count += 1

    if pattern_count == 0:
        console.print(
            Panel(
                f"[dim]No patterns found with min_occurrences={min_occurrences}.[/dim]",
                title="Detected Patterns",
                border_style="dim",
            )
        )
    else:
        console.print(table)
        console.print(f"\n[dim]Found {pattern_count} patterns[/dim]")


@memory_app.command("recommend")
def recommend_command(
    category: str = typer.Argument(..., help="Category for recommendations (e.g., schema_drift, test_failure)"),
    context: str = typer.Option(
        "{}",
        "--context",
        "-x",
        help="JSON context string (e.g., '{\"class_name\": \"MyClass\"}')",
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        "-n",
        help="Maximum number of recommendations to show",
    ),
) -> None:
    """
    Get recommendations for a category/context.

    Uses the RecommendationEngine to find similar past issues
    and suggest fixes based on historical patterns.

    Example:
        swarm-attack memory recommend schema_drift --context '{"class_name": "UserConfig"}'
        swarm-attack memory recommend test_failure --context '{"test_path": "tests/test_auth.py"}'
    """
    import json as json_module

    from swarm_attack.memory.recommendations import RecommendationEngine
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    engine = RecommendationEngine(store)

    # Parse context JSON
    try:
        context_dict = json_module.loads(context)
    except json_module.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON context: {e}[/red]")
        raise typer.Exit(1)

    # Get recommendations - use category-specific method if available
    if hasattr(engine, 'get_recommendations_by_category'):
        recommendations = engine.get_recommendations_by_category(
            category=category,
            context=context_dict,
            limit=limit,
        )
    else:
        # Fall back to simpler API
        context_dict["category"] = category
        recommendations = engine.get_recommendations(
            current_issue=context_dict,
            limit=limit,
        )

    if not recommendations:
        console.print(
            Panel(
                f"[dim]No recommendations found for category '{category}'.[/dim]",
                title="Recommendations",
                border_style="dim",
            )
        )
        return

    # Create table for recommendations
    table = Table(title=f"Recommendations for {category}")
    table.add_column("#", style="dim", width=3)
    table.add_column("Recommendation", style="green", max_width=60)
    table.add_column("Confidence", style="magenta")

    for i, rec in enumerate(recommendations, 1):
        confidence_pct = f"{rec.confidence * 100:.0f}%"
        table.add_row(
            str(i),
            rec.action,
            confidence_pct,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(recommendations)} recommendations[/dim]")


@memory_app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Search query"),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Maximum results to show",
    ),
) -> None:
    """
    Search memory entries semantically.

    Uses weighted keyword matching to find relevant memory entries.
    Results are sorted by relevance score.

    Example:
        swarm-attack memory search "authentication error"
        swarm-attack memory search "schema drift" --category schema_drift
        swarm-attack memory search "test failure" --limit 5
    """
    from swarm_attack.memory.search import SemanticSearch
    from swarm_attack.memory.store import MemoryStore

    store = MemoryStore.load()
    searcher = SemanticSearch(store)

    # Perform search
    results = searcher.search(
        query=query,
        category=category,
        limit=limit,
    )

    if not results:
        console.print(
            Panel(
                f"[dim]No results found for '{query}'.[/dim]",
                title="Search Results",
                border_style="dim",
            )
        )
        return

    # Create table for results
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Score", style="magenta", width=6)
    table.add_column("Category", style="cyan", width=15)
    table.add_column("Feature", style="green", width=15)
    table.add_column("Keywords", style="yellow", max_width=30)
    table.add_column("ID", style="dim", width=12)

    for result in results:
        score_str = f"{result.score:.2f}"
        keywords_str = ", ".join(result.matched_keywords[:5])
        if len(result.matched_keywords) > 5:
            keywords_str += f" +{len(result.matched_keywords) - 5}"

        table.add_row(
            score_str,
            result.entry.category,
            result.entry.feature_id,
            keywords_str,
            result.entry.id[:12],
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(results)} matching entries[/dim]")


# Alias for backwards compatibility
app = memory_app
