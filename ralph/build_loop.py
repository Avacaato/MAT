"""Ralph Build Loop for MAT.

The autonomous build loop iterates through user stories in prd.json,
implementing and verifying each one until all stories pass or fail.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.developer import DeveloperAgent, UserStory
from agents.qa import QATesterAgent
from agents.scrum_master import ScrumMasterAgent, StoryStatus
from config import get_settings
from utils.git_ops import auto_commit_story
from utils.logger import (
    create_progress_tracker,
    log_agent_action,
    log_build_complete,
    log_build_start,
)

logger = logging.getLogger(__name__)


class BuildLoopError(Exception):
    """Base exception for build loop errors."""


class PRDLoadError(BuildLoopError):
    """Error loading or parsing prd.json."""


@dataclass
class BuildResult:
    """Result of a build loop execution.

    Attributes:
        success: True if all stories passed.
        total_stories: Total number of stories processed.
        completed_stories: Number of stories that passed.
        failed_stories: Number of stories that failed.
        failed_story_ids: List of IDs of failed stories.
        errors: List of error messages encountered.
    """

    success: bool
    total_stories: int
    completed_stories: int
    failed_stories: int
    failed_story_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "total_stories": self.total_stories,
            "completed_stories": self.completed_stories,
            "failed_stories": self.failed_stories,
            "failed_story_ids": self.failed_story_ids,
            "errors": self.errors,
        }


@dataclass
class BuildLoop:
    """Autonomous build loop for implementing user stories.

    Iterates through stories in prd.json, using Developer and QA agents
    to implement and verify each one.

    Attributes:
        prd_path: Path to prd.json file.
        max_retries: Maximum retry attempts per story.
        developer_agent: Agent for implementing stories.
        qa_agent: Agent for verifying stories.
        scrum_master: Agent for tracking progress and blockers.
    """

    prd_path: Path = field(default_factory=lambda: Path("prd.json"))
    max_retries: int = 3
    developer_agent: DeveloperAgent = field(default_factory=DeveloperAgent)
    qa_agent: QATesterAgent = field(default_factory=QATesterAgent)
    scrum_master: ScrumMasterAgent = field(default_factory=ScrumMasterAgent)
    _prd_data: dict[str, Any] | None = field(default=None, repr=False)

    def _get_prd_path(self) -> Path:
        """Get the full path to prd.json."""
        if self.prd_path.is_absolute():
            return self.prd_path
        settings = get_settings()
        return Path(settings.project_dir) / self.prd_path

    def load_prd(self) -> dict[str, Any]:
        """Load and validate prd.json.

        Returns:
            Parsed PRD data.

        Raises:
            PRDLoadError: If prd.json is missing or malformed.
        """
        prd_path = self._get_prd_path()

        if not prd_path.exists():
            raise PRDLoadError(f"prd.json not found at {prd_path}")

        try:
            with open(prd_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise PRDLoadError(f"Invalid JSON in prd.json: {e}") from e

        # Validate required fields
        if "userStories" not in data:
            raise PRDLoadError("prd.json missing 'userStories' field")

        if not isinstance(data["userStories"], list):
            raise PRDLoadError("'userStories' must be a list")

        self._prd_data = data
        log_agent_action("BuildLoop", "Loaded PRD", f"{len(data['userStories'])} stories")
        result: dict[str, Any] = data
        return result

    def save_prd(self) -> None:
        """Save current PRD data back to prd.json."""
        if self._prd_data is None:
            return

        prd_path = self._get_prd_path()
        with open(prd_path, "w", encoding="utf-8") as f:
            json.dump(self._prd_data, f, indent=2)
            f.write("\n")  # Add trailing newline
        log_agent_action("BuildLoop", "Saved PRD", str(prd_path))

    def mark_story_passed(self, story_id: str) -> None:
        """Mark a story as passed in prd.json.

        Args:
            story_id: ID of the story to mark as passed.
        """
        if self._prd_data is None:
            return

        for story in self._prd_data.get("userStories", []):
            if story.get("id") == story_id:
                story["passes"] = True
                break

        self.save_prd()

    def get_next_story(self) -> dict[str, Any] | None:
        """Get the next story with passes=false.

        Returns:
            Story dict, or None if all stories are complete.
        """
        if self._prd_data is None:
            return None

        # Sort by priority and return first with passes=false
        stories: list[dict[str, Any]] = self._prd_data.get("userStories", [])
        stories_sorted = sorted(stories, key=lambda s: s.get("priority", 999))

        for story in stories_sorted:
            if not story.get("passes", False):
                return story
        return None

    def get_remaining_count(self) -> int:
        """Get count of stories with passes=false.

        Returns:
            Number of remaining stories.
        """
        if self._prd_data is None:
            return 0

        return sum(
            1 for s in self._prd_data.get("userStories", [])
            if not s.get("passes", False)
        )

    def implement_story(
        self, story_data: dict[str, Any]
    ) -> tuple[bool, list[str], str]:
        """Implement a single story using Developer and QA agents.

        Args:
            story_data: Story dict from prd.json.

        Returns:
            Tuple of (success, written_files, failure_reason).
        """
        story_id = story_data.get("id", "unknown")
        story_title = story_data.get("title", "untitled")

        log_agent_action("BuildLoop", "Implementing", f"{story_id} - {story_title}")

        # Create UserStory for Developer agent
        story = UserStory.from_dict(story_data)

        try:
            # Implementation phase
            written_files = self.developer_agent.implement_story(story)
            log_agent_action(
                "BuildLoop",
                "Files written",
                f"{len(written_files)} files for {story_id}",
            )
        except Exception as e:
            reason = f"Implementation failed: {e}"
            logger.error(f"[BuildLoop] {story_id} - {reason}")
            return False, [], reason

        try:
            # Verification phase
            report = self.qa_agent.verify_story(story_data, written_files)

            if report.overall_passed:
                log_agent_action("BuildLoop", "Verification passed", story_id)
                return True, written_files, ""
            else:
                reason = f"Verification failed: {report.summary}"
                logger.warning(f"[BuildLoop] {story_id} - {reason}")
                return False, written_files, reason

        except Exception as e:
            reason = f"Verification error: {e}"
            logger.error(f"[BuildLoop] {story_id} - {reason}")
            return False, written_files, reason

    def run_story_with_retries(
        self, story_data: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Run a story implementation with retry logic.

        Args:
            story_data: Story dict from prd.json.

        Returns:
            Tuple of (success, written_files).
        """
        story_id = story_data.get("id", "unknown")
        failure_reasons: list[str] = []

        for attempt in range(1, self.max_retries + 1):
            log_agent_action(
                "BuildLoop",
                f"Attempt {attempt}/{self.max_retries}",
                story_id,
            )

            success, written_files, failure_reason = self.implement_story(story_data)

            if success:
                return True, written_files

            failure_reasons.append(f"Attempt {attempt}: {failure_reason}")

            # Clear agent state for retry
            self.developer_agent.clear_history()
            self.qa_agent.reset()

        # All retries exhausted
        all_reasons = "; ".join(failure_reasons)
        logger.error(
            f"[BuildLoop] {story_id} failed after {self.max_retries} attempts: {all_reasons}"
        )
        return False, []

    def should_continue(self) -> bool:
        """Check if the build should continue.

        Returns:
            True if there are actionable stories, False if all failed or done.
        """
        return self.scrum_master.should_continue_build(self.max_retries)

    def run(self) -> BuildResult:
        """Run the autonomous build loop.

        Iterates through all stories with passes=false, implementing and
        verifying each one. Retries failed stories up to max_retries times.

        Returns:
            BuildResult with final status and statistics.
        """
        # Load PRD
        try:
            prd_data = self.load_prd()
        except PRDLoadError as e:
            logger.error(f"[BuildLoop] Failed to load PRD: {e}")
            return BuildResult(
                success=False,
                total_stories=0,
                completed_stories=0,
                failed_stories=0,
                errors=[str(e)],
            )

        # Initialize scrum master with stories
        self.scrum_master.load_stories(prd_data)

        project_name = prd_data.get("project", "Unknown Project")
        total_stories = len(prd_data.get("userStories", []))
        already_passed = sum(
            1 for s in prd_data.get("userStories", [])
            if s.get("passes", False)
        )

        log_build_start(project_name, total_stories)

        # Create progress tracker
        progress = create_progress_tracker(total_stories, already_passed)

        completed_count = already_passed
        failed_story_ids: list[str] = []
        errors: list[str] = []

        with progress:
            while True:
                # Get next story to work on
                story = self.scrum_master.get_next_story()

                if story is None:
                    # No more pending stories
                    break

                story_id = story.id
                story_title = story.title

                # Check if this story should be skipped
                if story.status == StoryStatus.FAILED and story.attempt_count >= self.max_retries:
                    log_agent_action("BuildLoop", "Skipping failed story", story_id)
                    continue

                progress.begin_story(story_id, story_title)

                # Get the story data from PRD
                story_data: dict[str, Any] | None = None
                if self._prd_data is not None:
                    for s in self._prd_data.get("userStories", []):
                        if s.get("id") == story_id:
                            story_data = s
                            break

                if story_data is None:
                    logger.error(f"[BuildLoop] Story {story_id} not found in PRD")
                    self.scrum_master.mark_story_failed(story_id, "Story not found in PRD")
                    progress.fail_story("Story not found in PRD")
                    failed_story_ids.append(story_id)
                    continue

                # Implement the story with retries
                success, written_files = self.run_story_with_retries(story_data)

                if success:
                    # Mark as passed and commit
                    self.mark_story_passed(story_id)
                    self.scrum_master.mark_story_completed(story_id)
                    progress.complete_story()
                    completed_count += 1

                    # Auto-commit the changes
                    auto_commit_story(story_id, story_title, written_files)
                else:
                    # Mark as failed
                    self.scrum_master.mark_story_failed(
                        story_id, f"Failed after {self.max_retries} attempts"
                    )
                    progress.fail_story(f"Failed after {self.max_retries} attempts")
                    failed_story_ids.append(story_id)
                    errors.append(f"{story_id}: Failed after {self.max_retries} attempts")

                # Check if we should continue
                if not self.should_continue():
                    log_agent_action(
                        "BuildLoop",
                        "Stopping",
                        "All remaining stories have failed",
                    )
                    break

        # Log completion
        log_build_complete(progress)

        # Calculate results
        failed_count = len(failed_story_ids)
        success = failed_count == 0 and completed_count == total_stories

        return BuildResult(
            success=success,
            total_stories=total_stories,
            completed_stories=completed_count,
            failed_stories=failed_count,
            failed_story_ids=failed_story_ids,
            errors=errors,
        )


def run_build_loop(
    prd_path: str | Path | None = None,
    max_retries: int = 3,
) -> BuildResult:
    """Convenience function to run the build loop.

    Args:
        prd_path: Optional path to prd.json (defaults to project root).
        max_retries: Maximum retry attempts per story.

    Returns:
        BuildResult with final status.
    """
    loop = BuildLoop(max_retries=max_retries)
    if prd_path:
        loop.prd_path = Path(prd_path)
    return loop.run()
