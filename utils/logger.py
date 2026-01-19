"""Progress tracking and logging utilities for MAT."""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from config.settings import get_settings

# Module-level console for rich output
_console: Console | None = None

# Module-level file handler for cleanup
_file_handler: logging.FileHandler | None = None


def get_console() -> Console:
    """Get the global console instance."""
    global _console
    if _console is None:
        _console = Console()
    return _console


def _get_log_file_path() -> Path:
    """Get the path to the build log file."""
    settings = get_settings()
    return Path(settings.project_dir) / "build.log"


def setup_logging(verbose: bool | None = None) -> logging.Logger:
    """
    Set up logging with both console and file output.

    Args:
        verbose: Override verbose mode. If None, uses settings.

    Returns:
        Configured logger instance.
    """
    global _file_handler

    settings = get_settings()
    if verbose is None:
        verbose = settings.verbose

    # Create logger
    logger = logging.getLogger("mat")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with rich formatting
    console_handler = RichHandler(
        console=get_console(),
        show_time=True,
        show_path=verbose,
        rich_tracebacks=True,
    )
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler for build.log
    log_file = _get_log_file_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    _file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    _file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _file_handler.setFormatter(file_format)
    logger.addHandler(_file_handler)

    return logger


def get_logger() -> logging.Logger:
    """
    Get the MAT logger instance.

    If not already set up, configures with default settings.

    Returns:
        The MAT logger.
    """
    logger = logging.getLogger("mat")
    if not logger.handlers:
        return setup_logging()
    return logger


def log_agent_action(agent_name: str, action: str, details: str = "") -> None:
    """
    Log an agent action with consistent formatting.

    Args:
        agent_name: Name of the agent performing the action.
        action: The action being performed (e.g., "thinking", "writing", "verifying").
        details: Optional additional details about the action.
    """
    logger = get_logger()
    message = f"[{agent_name}] {action}"
    if details:
        message += f": {details}"
    logger.info(message)


def log_agent_decision(agent_name: str, decision: str, reasoning: str = "") -> None:
    """
    Log an agent decision with reasoning.

    Args:
        agent_name: Name of the agent making the decision.
        decision: The decision made.
        reasoning: Optional reasoning for the decision.
    """
    logger = get_logger()
    message = f"[{agent_name}] Decision: {decision}"
    logger.info(message)
    if reasoning:
        logger.debug(f"[{agent_name}] Reasoning: {reasoning}")


def log_verbose(message: str, **kwargs: Any) -> None:
    """
    Log a message only in verbose mode.

    Args:
        message: The message to log.
        **kwargs: Additional context to include in debug output.
    """
    logger = get_logger()
    if kwargs:
        context = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        message = f"{message} ({context})"
    logger.debug(message)


@dataclass
class StoryProgress:
    """Tracks progress through user stories."""

    total_stories: int
    completed_stories: int = 0
    current_story_id: str = ""
    current_story_title: str = ""
    failed_stories: list[str] = field(default_factory=list)
    _progress: Progress | None = field(default=None, repr=False)
    _task_id: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize the progress bar."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=get_console(),
        )
        self._task_id = self._progress.add_task(
            "Building stories...",
            total=self.total_stories,
            completed=self.completed_stories,
        )

    def start(self) -> "StoryProgress":
        """Start the progress display. Returns self for chaining."""
        if self._progress is not None:
            self._progress.start()
        return self

    def stop(self) -> None:
        """Stop the progress display."""
        if self._progress is not None:
            self._progress.stop()

    def __enter__(self) -> "StoryProgress":
        """Context manager entry."""
        return self.start()

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.stop()

    def begin_story(self, story_id: str, story_title: str) -> None:
        """
        Mark beginning of work on a story.

        Args:
            story_id: The ID of the story (e.g., "US-005").
            story_title: The title of the story.
        """
        self.current_story_id = story_id
        self.current_story_title = story_title
        if self._progress is not None and self._task_id is not None:
            self._progress.update(
                self._task_id,
                description=f"[cyan]{story_id}[/cyan]: {story_title}",
            )
        log_agent_action("Build", "Starting story", f"{story_id} - {story_title}")

    def complete_story(self) -> None:
        """Mark current story as completed."""
        self.completed_stories += 1
        if self._progress is not None and self._task_id is not None:
            self._progress.update(self._task_id, advance=1)
        log_agent_action(
            "Build",
            "Completed story",
            f"{self.current_story_id} ({self.completed_stories}/{self.total_stories})",
        )
        self.current_story_id = ""
        self.current_story_title = ""

    def fail_story(self, reason: str = "") -> None:
        """
        Mark current story as failed.

        Args:
            reason: Optional reason for failure.
        """
        if self.current_story_id:
            self.failed_stories.append(self.current_story_id)
        if self._progress is not None and self._task_id is not None:
            self._progress.update(self._task_id, advance=1)
        logger = get_logger()
        message = f"Failed story {self.current_story_id}"
        if reason:
            message += f": {reason}"
        logger.error(message)
        self.current_story_id = ""
        self.current_story_title = ""

    def get_summary(self) -> str:
        """
        Get a summary of progress.

        Returns:
            Human-readable summary of build progress.
        """
        failed_count = len(self.failed_stories)
        passed_count = self.completed_stories - failed_count
        lines = [
            f"Build Progress: {self.completed_stories}/{self.total_stories} stories processed",
            f"  ✓ Passed: {passed_count}",
            f"  ✗ Failed: {failed_count}",
        ]
        if self.failed_stories:
            lines.append(f"  Failed stories: {', '.join(self.failed_stories)}")
        return "\n".join(lines)


def create_progress_tracker(total_stories: int, completed: int = 0) -> StoryProgress:
    """
    Create a new story progress tracker.

    Args:
        total_stories: Total number of stories in the build.
        completed: Number of already completed stories.

    Returns:
        StoryProgress instance for tracking build progress.
    """
    return StoryProgress(total_stories=total_stories, completed_stories=completed)


def log_build_start(project_name: str, total_stories: int) -> None:
    """
    Log the start of a build.

    Args:
        project_name: Name of the project being built.
        total_stories: Total number of stories to build.
    """
    logger = get_logger()
    console = get_console()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"\n[bold blue]MAT Build Started[/bold blue] - {timestamp}")
    console.print(f"Project: [cyan]{project_name}[/cyan]")
    console.print(f"Stories: [yellow]{total_stories}[/yellow]\n")

    logger.info(f"=== BUILD STARTED: {project_name} ({total_stories} stories) ===")


def log_build_complete(progress: StoryProgress) -> None:
    """
    Log build completion with summary.

    Args:
        progress: The progress tracker with final stats.
    """
    logger = get_logger()
    console = get_console()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    failed_count = len(progress.failed_stories)

    if failed_count == 0:
        console.print(f"\n[bold green]✓ BUILD COMPLETE[/bold green] - {timestamp}")
    else:
        console.print(f"\n[bold yellow]⚠ BUILD FINISHED WITH FAILURES[/bold yellow] - {timestamp}")

    console.print(progress.get_summary())
    logger.info(f"=== BUILD COMPLETE ===\n{progress.get_summary()}")
