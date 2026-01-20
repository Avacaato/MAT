"""MAT CLI entry point.

Provides command-line interface for MAT operations:
- mat init: Start a new project with discovery interview
- mat build: Run Ralph build loop
- mat status: Show current build progress
"""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from config import get_settings, reload_settings
from ralph import BuildLoop, BuildLoopError
from utils.logger import get_logger, setup_logging
from workflows import PRDGenerator

# Create Typer app
app = typer.Typer(
    name="mat",
    help="MAT (Multi-Agent Toolkit) - Local LLM Build Framework",
    add_completion=False,
)

console = Console()


def _get_prd_path(project_dir: str | None = None) -> Path:
    """Get the path to prd.json.

    Args:
        project_dir: Optional project directory override.

    Returns:
        Path to prd.json file.
    """
    if project_dir:
        return Path(project_dir) / "prd.json"
    settings = get_settings()
    return Path(settings.project_dir) / "prd.json"


def _load_prd_data(prd_path: Path) -> dict[str, object] | None:
    """Load PRD data from file.

    Args:
        prd_path: Path to prd.json file.

    Returns:
        Parsed PRD data or None if not found.
    """
    if not prd_path.exists():
        return None
    try:
        with open(prd_path, "r", encoding="utf-8") as f:
            data: dict[str, object] = json.load(f)
            return data
    except (json.JSONDecodeError, OSError):
        return None


@app.command()
def init(
    project_dir: Optional[str] = typer.Option(
        None,
        "--project-dir",
        "-p",
        help="Project directory (defaults to current directory)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """Start a new project with discovery interview.

    This command runs an interactive discovery interview to gather project
    requirements, then generates a Product Requirements Document (PRD).

    The PRD is saved to tasks/prd.md and can be converted to prd.json for
    the build loop using the PRDToJsonConverter.
    """
    # Set up logging and config
    if project_dir:
        os.environ["MAT_PROJECT_DIR"] = project_dir
        reload_settings()

    setup_logging(verbose=verbose)
    logger = get_logger()

    console.print("\n[bold blue]MAT Project Initialization[/bold blue]\n")

    try:
        # Step 1: Get project name first
        project_name = typer.prompt(
            "What do you want to name this project? (e.g., 'habit-tracker', 'invoice-app')"
        )
        console.print()

        # Step 2: Get initial project description
        console.print(
            "[cyan]Tell me about what you want to build.[/cyan]\n"
            "Describe your idea in a few sentences - what is it, what problem "
            "does it solve, who is it for?\n"
        )
        try:
            initial_idea = typer.prompt("Your idea")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1) from None

        console.print()
        console.print(
            "[dim]Great! Now I'll ask a few follow-up questions to understand "
            "your project better.[/dim]\n"
        )

        # Create PRD generator and start interview with context
        prd_gen = PRDGenerator()

        # Start the discovery interview
        opening_message = prd_gen.start_discovery()

        # Feed the initial idea as the first response (for the "problem" question)
        response = prd_gen.process_user_input(initial_idea)
        console.print(f"[cyan]PM Agent:[/cyan] {response}\n")

        # Run remaining interview loop
        while not prd_gen.is_discovery_complete():
            try:
                user_input = typer.prompt("You")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Interview cancelled.[/yellow]")
                raise typer.Exit(1) from None

            response = prd_gen.process_user_input(user_input)
            console.print(f"\n[cyan]PM Agent:[/cyan] {response}\n")

        # Discovery complete
        console.print("\n[bold]Discovery complete![/bold]")

        # Generate PRD
        console.print("\n[dim]Generating PRD...[/dim]")
        prd = prd_gen.generate_prd(project_name)
        saved_path = prd_gen.save_prd()

        console.print(f"\n[green]PRD saved to:[/green] {saved_path}")
        console.print(f"[green]User stories:[/green] {len(prd.user_stories)}")
        console.print(
            "\n[dim]Next step: Convert PRD to prd.json and run 'mat build'[/dim]"
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(1) from None
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def build(
    prd_file: Optional[str] = typer.Option(
        None,
        "--prd",
        "-f",
        help="Path to prd.json file (defaults to prd.json in project root)",
    ),
    project_dir: Optional[str] = typer.Option(
        None,
        "--project-dir",
        "-p",
        help="Project directory (defaults to current directory)",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        "-r",
        help="Maximum retry attempts per story",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
) -> None:
    """Run Ralph build loop.

    This command runs the autonomous build loop which iterates through all
    user stories in prd.json, implementing and verifying each one.

    The build loop will:
    1. Load stories from prd.json
    2. For each story with passes=false: implement, verify, mark complete
    3. Retry failed stories up to max-retries times
    4. Auto-commit after each successful story
    """
    # Set up logging and config
    if project_dir:
        os.environ["MAT_PROJECT_DIR"] = project_dir
        reload_settings()

    setup_logging(verbose=verbose)
    logger = get_logger()

    # Determine PRD path
    prd_path = Path(prd_file) if prd_file else _get_prd_path(project_dir)

    console.print("\n[bold blue]MAT Build Loop[/bold blue]\n")

    # Check if prd.json exists
    if not prd_path.exists():
        console.print(f"[red]Error:[/red] prd.json not found at {prd_path}")
        console.print(
            "[dim]Run 'mat init' to create a project, "
            "then convert PRD to prd.json[/dim]"
        )
        raise typer.Exit(1)

    console.print(f"[dim]Loading PRD from:[/dim] {prd_path}")

    try:
        # Create and run build loop
        build_loop = BuildLoop(prd_path=prd_path, max_retries=max_retries)
        result = build_loop.run()

        # Display results
        if result.success:
            console.print("\n[bold green]Build completed successfully![/bold green]")
        else:
            console.print("\n[bold yellow]Build finished with issues.[/bold yellow]")

        passed_count = result.completed_stories
        total_count = result.total_stories
        console.print(f"[dim]Stories:[/dim] {passed_count}/{total_count} passed")

        if result.failed_story_ids:
            console.print(f"[red]Failed:[/red] {', '.join(result.failed_story_ids)}")

        if result.errors:
            console.print("\n[yellow]Errors:[/yellow]")
            for error in result.errors:
                console.print(f"  - {error}")

        # Exit with appropriate code (don't raise, just return for success)
        if not result.success:
            raise typer.Exit(1)

    except BuildLoopError as e:
        logger.error(f"Build loop error: {e}")
        console.print(f"\n[red]Build Error:[/red] {e}")
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        console.print("\n[yellow]Build interrupted.[/yellow]")
        raise typer.Exit(1) from None
    except typer.Exit:
        # Re-raise typer exits (don't catch them as generic exceptions)
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def status(
    prd_file: Optional[str] = typer.Option(
        None,
        "--prd",
        "-f",
        help="Path to prd.json file (defaults to prd.json in project root)",
    ),
    project_dir: Optional[str] = typer.Option(
        None,
        "--project-dir",
        "-p",
        help="Project directory (defaults to current directory)",
    ),
) -> None:
    """Show current build progress.

    Displays the status of all user stories in prd.json, showing which
    stories have passed, which are pending, and overall progress.
    """
    # Set up config
    if project_dir:
        os.environ["MAT_PROJECT_DIR"] = project_dir
        reload_settings()

    # Determine PRD path
    prd_path = Path(prd_file) if prd_file else _get_prd_path(project_dir)

    console.print("\n[bold blue]MAT Build Status[/bold blue]\n")

    # Check if prd.json exists
    if not prd_path.exists():
        console.print(f"[red]Error:[/red] prd.json not found at {prd_path}")
        console.print(
            "[dim]Run 'mat init' to create a project, "
            "then convert PRD to prd.json[/dim]"
        )
        raise typer.Exit(1)

    # Load PRD data
    prd_data = _load_prd_data(prd_path)
    if prd_data is None:
        console.print(f"[red]Error:[/red] Could not read prd.json at {prd_path}")
        raise typer.Exit(1)

    # Extract information
    project_name = str(prd_data.get("project", "Unknown Project"))
    branch_name = str(prd_data.get("branchName", "N/A"))
    stories_raw = prd_data.get("userStories", [])
    stories: list[dict[str, object]] = stories_raw if isinstance(stories_raw, list) else []

    # Calculate stats
    total = len(stories)
    passed = sum(1 for s in stories if s.get("passes", False))
    pending = total - passed

    # Display project info
    console.print(f"[bold]Project:[/bold] {project_name}")
    console.print(f"[bold]Branch:[/bold] {branch_name}")
    console.print(f"[bold]PRD:[/bold] {prd_path}")
    console.print()

    # Display progress bar
    if total > 0:
        progress_pct = (passed / total) * 100
        filled = int(progress_pct / 5)  # 20 chars wide
        bar = "[green]" + "█" * filled + "[/green]" + "░" * (20 - filled)
        console.print(f"Progress: {bar} {progress_pct:.0f}%")
        console.print(f"  Passed: [green]{passed}[/green] / Pending: [yellow]{pending}[/yellow]")
        console.print()

    # Display story table
    table = Table(title="User Stories")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Priority", justify="right")
    table.add_column("Status", justify="center")

    # Sort by priority
    def get_priority(s: dict[str, object]) -> int:
        """Get priority as int, defaulting to 999."""
        p = s.get("priority", 999)
        if isinstance(p, int):
            return p
        if isinstance(p, float):
            return int(p)
        if isinstance(p, str) and p.isdigit():
            return int(p)
        return 999

    sorted_stories = sorted(stories, key=get_priority)

    for story in sorted_stories:
        story_id = str(story.get("id", "?"))
        title = str(story.get("title", "Untitled"))
        priority = str(story.get("priority", "?"))
        passes = story.get("passes", False)
        status_str = "[green]✓ Passed[/green]" if passes else "[yellow]○ Pending[/yellow]"
        table.add_row(story_id, title, priority, status_str)

    console.print(table)

    # Exit with appropriate code
    if pending > 0:
        raise typer.Exit(1)
    raise typer.Exit(0)


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
