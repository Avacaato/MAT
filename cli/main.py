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
from openai import OpenAI
from rich.console import Console
from rich.table import Table

from config import get_settings, reload_settings
from ralph import BuildLoop, BuildLoopError
from utils.logger import get_logger, setup_logging
from workflows import PRDGenerator, PRDToJsonConverter

# Create Typer app
app = typer.Typer(
    name="mat",
    help="MAT (Multi-Agent Toolkit) - Local LLM Build Framework",
    add_completion=False,
)

console = Console()


def _detect_ollama_models(ollama_url: str = "http://localhost:11434") -> list[str]:
    """Detect available Ollama models."""
    try:
        client = OpenAI(base_url=f"{ollama_url}/v1", api_key="ollama")
        response = client.models.list()
        return [model.id for model in response.data]
    except Exception:
        return []


def _create_mat_config(project_dir: Path, model: str, ollama_url: str = "http://localhost:11434") -> Path | None:
    """Create .mat-config file in project directory.

    Returns the config path if successful, None if permission denied.
    Falls back to environment variables if file cannot be created.
    """
    config_path = project_dir / ".mat-config"
    config_content = f"""model={model}
ollama_url={ollama_url}
project_dir={project_dir}
timeout=300
verbose=false
max_retries=3
"""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        return config_path
    except (PermissionError, OSError):
        # Fall back to environment variables
        os.environ["MAT_MODEL"] = model
        os.environ["MAT_OLLAMA_URL"] = ollama_url
        os.environ["MAT_PROJECT_DIR"] = str(project_dir)
        return None


def _select_model(models: list[str]) -> str:
    """Let user select a model from available options."""
    console.print("\n[bold]Available Ollama models:[/bold]")
    for i, model in enumerate(models, 1):
        console.print(f"  {i}. {model}")

    while True:
        try:
            choice = typer.prompt("\nSelect model number", default="1")
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
            console.print("[red]Invalid selection. Try again.[/red]")
        except ValueError:
            console.print("[red]Please enter a number.[/red]")


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
    skip_build: bool = typer.Option(
        False,
        "--skip-build",
        help="Skip the build step after PRD generation",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Ollama model to use (auto-detected if not specified)",
    ),
) -> None:
    """Start a new project with discovery interview.

    This command runs the full MAT workflow:
    1. Detect and select Ollama model
    2. Create .mat-config
    3. Run discovery interview
    4. Generate PRD
    5. Convert PRD to prd.json
    6. Optionally start the build loop
    """
    # Determine project directory
    proj_dir = Path(project_dir) if project_dir else Path.cwd()

    # Set up logging and config
    if project_dir:
        os.environ["MAT_PROJECT_DIR"] = project_dir
        reload_settings()

    setup_logging(verbose=verbose)
    logger = get_logger()

    console.print("\n[bold blue]MAT Project Initialization[/bold blue]\n")

    try:
        # Step 1: Detect Ollama models
        console.print("[dim]Detecting Ollama models...[/dim]")
        models = _detect_ollama_models()

        if not models:
            console.print("[red]Error:[/red] No Ollama models found.")
            console.print("[dim]Make sure Ollama is running and has models installed.[/dim]")
            console.print("[dim]Run: ollama pull codellama[/dim]")
            raise typer.Exit(1)

        # Step 2: Select model
        if model and model in models:
            selected_model = model
            console.print(f"[dim]Using model:[/dim] {selected_model}")
        elif model:
            console.print(f"[yellow]Warning:[/yellow] Model '{model}' not found.")
            selected_model = _select_model(models)
        else:
            selected_model = _select_model(models)

        console.print(f"\n[green]Selected model:[/green] {selected_model}")

        # Step 3: Create .mat-config (or fall back to env vars)
        config_path = _create_mat_config(proj_dir, selected_model)
        if config_path:
            console.print(f"[dim]Created config:[/dim] {config_path}")
        else:
            console.print("[dim]Using environment variables for config (no write permission)[/dim]")

        # Reload settings with new config
        reload_settings()

        # Step 4: Get project name
        console.print()
        project_name = typer.prompt(
            "What do you want to name this project? (e.g., 'habit-tracker', 'invoice-app')"
        )
        console.print()

        # Step 5: Get initial project description
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

        # Step 6: Run discovery interview
        prd_gen = PRDGenerator()
        opening_message = prd_gen.start_discovery()

        # Feed the initial idea as the first response
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

        # Step 7: Generate PRD
        console.print("\n[bold]Discovery complete![/bold]")
        console.print("\n[dim]Generating PRD...[/dim]")
        prd = prd_gen.generate_prd(project_name)
        saved_path = prd_gen.save_prd()

        console.print(f"\n[green]PRD saved to:[/green] {saved_path}")
        console.print(f"[green]User stories:[/green] {len(prd.user_stories)}")

        # Step 8: Convert PRD to prd.json
        console.print("\n[dim]Converting PRD to prd.json...[/dim]")
        converter = PRDToJsonConverter()
        prd_json_path = proj_dir / "prd.json"
        prd_json = converter.convert(str(saved_path), str(prd_json_path))

        console.print(f"[green]prd.json created:[/green] {prd_json_path}")
        console.print(f"[dim]Stories ready for build:[/dim] {len(prd_json.user_stories)}")

        # Step 9: Ask about build
        if skip_build:
            console.print("\n[dim]Skipping build (--skip-build flag set)[/dim]")
            console.print("[dim]Run 'mat build' when ready to start the autonomous build loop[/dim]")
            return

        console.print()
        start_build = typer.confirm("Start the autonomous build now?", default=True)

        if not start_build:
            console.print("\n[dim]Run 'mat build' when ready to start the autonomous build loop[/dim]")
            return

        # Step 10: Run build loop
        console.print("\n[bold blue]Starting Build Loop[/bold blue]\n")
        build_loop = BuildLoop(prd_path=prd_json_path, max_retries=3)
        result = build_loop.run()

        # Display results
        if result.success:
            console.print("\n[bold green]Build completed successfully![/bold green]")
        else:
            console.print("\n[bold yellow]Build finished with issues.[/bold yellow]")

        console.print(f"[dim]Stories:[/dim] {result.completed_stories}/{result.total_stories} passed")

        if result.failed_story_ids:
            console.print(f"[red]Failed:[/red] {', '.join(result.failed_story_ids)}")

        if not result.success:
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(1) from None
    except typer.Exit:
        raise
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def convert(
    prd_file: Optional[str] = typer.Option(
        None,
        "--prd",
        "-f",
        help="Path to PRD markdown file (defaults to tasks/prd.md)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for prd.json (defaults to prd.json in project root)",
    ),
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
    """Convert PRD markdown to prd.json for the build loop.

    This command converts a PRD markdown file (typically tasks/prd.md) to the
    prd.json format required by the Ralph build loop.
    """
    # Set up logging and config
    if project_dir:
        os.environ["MAT_PROJECT_DIR"] = project_dir
        reload_settings()

    setup_logging(verbose=verbose)
    settings = get_settings()

    console.print("\n[bold blue]MAT PRD Converter[/bold blue]\n")

    # Determine paths
    if prd_file:
        input_path = Path(prd_file)
    else:
        input_path = Path(settings.project_dir) / "tasks" / "prd.md"

    if output:
        output_path = Path(output)
    else:
        output_path = Path(settings.project_dir) / "prd.json"

    # Check if input exists
    if not input_path.exists():
        console.print(f"[red]Error:[/red] PRD not found at {input_path}")
        console.print("[dim]Run 'mat init' first to create a PRD[/dim]")
        raise typer.Exit(1)

    console.print(f"[dim]Input:[/dim] {input_path}")
    console.print(f"[dim]Output:[/dim] {output_path}")

    try:
        # Convert PRD to JSON
        converter = PRDToJsonConverter()
        prd_json = converter.convert(str(input_path), str(output_path))

        # Display results
        story_count = len(prd_json.user_stories)
        console.print(f"\n[green]Converted successfully![/green]")
        console.print(f"[dim]Project:[/dim] {prd_json.project}")
        console.print(f"[dim]Branch:[/dim] {prd_json.branch_name}")
        console.print(f"[dim]Stories:[/dim] {story_count}")
        console.print(f"\n[dim]Now run 'mat build' to start the autonomous build loop[/dim]")

    except Exception as e:
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
