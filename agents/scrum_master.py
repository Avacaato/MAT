"""Scrum Master Agent for MAT.

The ScrumMasterAgent manages workflow, tracks story progress,
identifies blockers, and manages the build queue.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.base import BaseAgent
from llm.client import OllamaClient
from utils.logger import log_agent_action, log_agent_decision


class StoryStatus(Enum):
    """Status of a user story."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StoryState:
    """Tracks the state of a single user story."""

    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: int
    status: StoryStatus = StoryStatus.PENDING
    attempt_count: int = 0
    failure_reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "priority": self.priority,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "failure_reasons": self.failure_reasons,
            "blockers": self.blockers,
        }

    @classmethod
    def from_prd_story(cls, story: dict[str, Any]) -> "StoryState":
        """Create StoryState from PRD JSON story format.

        Args:
            story: Story dict from prd.json with keys like id, title, description, etc.

        Returns:
            StoryState instance initialized from the story data.
        """
        passes = story.get("passes", False)
        status = StoryStatus.COMPLETED if passes else StoryStatus.PENDING

        return cls(
            id=story.get("id", ""),
            title=story.get("title", ""),
            description=story.get("description", ""),
            acceptance_criteria=story.get("acceptanceCriteria", []),
            priority=story.get("priority", 999),
            status=status,
        )


@dataclass
class BuildQueue:
    """Manages the queue of stories to be built."""

    stories: list[StoryState] = field(default_factory=list)
    current_story_index: int = -1

    def load_from_prd(self, prd_data: dict[str, Any]) -> None:
        """Load stories from PRD JSON data.

        Args:
            prd_data: The parsed prd.json content.
        """
        self.stories = []
        user_stories = prd_data.get("userStories", [])
        for story in user_stories:
            self.stories.append(StoryState.from_prd_story(story))
        # Sort by priority
        self.stories.sort(key=lambda s: s.priority)
        self.current_story_index = -1

    def get_next_story(self) -> StoryState | None:
        """Get the next pending story from the queue.

        Returns:
            The next StoryState to work on, or None if queue is empty.
        """
        for i, story in enumerate(self.stories):
            if story.status == StoryStatus.PENDING:
                self.current_story_index = i
                return story
        return None

    def get_current_story(self) -> StoryState | None:
        """Get the currently active story.

        Returns:
            The current StoryState, or None if no story is active.
        """
        if 0 <= self.current_story_index < len(self.stories):
            return self.stories[self.current_story_index]
        return None

    def get_pending_count(self) -> int:
        """Get count of pending stories."""
        return sum(1 for s in self.stories if s.status == StoryStatus.PENDING)

    def get_completed_count(self) -> int:
        """Get count of completed stories."""
        return sum(1 for s in self.stories if s.status == StoryStatus.COMPLETED)

    def get_failed_count(self) -> int:
        """Get count of failed stories."""
        return sum(1 for s in self.stories if s.status == StoryStatus.FAILED)

    def get_blocked_count(self) -> int:
        """Get count of blocked stories."""
        return sum(1 for s in self.stories if s.status == StoryStatus.BLOCKED)

    def get_summary(self) -> dict[str, int]:
        """Get a summary of queue status.

        Returns:
            Dict with counts for each status.
        """
        return {
            "total": len(self.stories),
            "pending": self.get_pending_count(),
            "completed": self.get_completed_count(),
            "failed": self.get_failed_count(),
            "blocked": self.get_blocked_count(),
            "in_progress": sum(
                1 for s in self.stories if s.status == StoryStatus.IN_PROGRESS
            ),
        }


@dataclass
class BlockerAnalysis:
    """Analysis of a blocker and suggested solutions."""

    blocker: str
    severity: str  # "low", "medium", "high", "critical"
    suggested_solutions: list[str]
    requires_human_intervention: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "blocker": self.blocker,
            "severity": self.severity,
            "suggested_solutions": self.suggested_solutions,
            "requires_human_intervention": self.requires_human_intervention,
        }


SCRUM_MASTER_SYSTEM_PROMPT = """You are a Scrum Master agent managing software development workflow.

Your responsibilities:
1. Track story completion status and progress
2. Identify blockers and suggest solutions
3. Manage the build queue and prioritization
4. Report progress and status updates

Guidelines:
- Be concise and actionable in your suggestions
- Prioritize unblocking the team over perfect solutions
- Flag critical issues that need human intervention
- Keep the build moving forward

When analyzing blockers, consider:
- Technical dependencies (missing files, APIs, etc.)
- Resource constraints (model limitations, timeout issues)
- Logic errors (test failures, type errors)
- External dependencies (network, services)

When suggesting solutions, provide concrete next steps."""


@dataclass
class ScrumMasterAgent(BaseAgent):
    """Scrum Master agent for workflow management.

    Tracks story progress, identifies blockers, and manages the build queue.

    Attributes:
        build_queue: The queue of stories being managed.
    """

    name: str = field(default="Scrum Master")
    role: str = field(default="Manage workflow and track progress")
    system_prompt: str = field(default=SCRUM_MASTER_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    build_queue: BuildQueue = field(default_factory=BuildQueue)

    def load_stories(self, prd_data: dict[str, Any]) -> None:
        """Load stories from PRD data into the build queue.

        Args:
            prd_data: The parsed prd.json content.
        """
        self.build_queue.load_from_prd(prd_data)
        log_agent_action(
            self.name,
            "Loaded stories",
            f"{len(self.build_queue.stories)} stories in queue",
        )

    def get_next_story(self) -> StoryState | None:
        """Get the next story to work on.

        Returns:
            The next pending StoryState, or None if no stories remain.
        """
        story = self.build_queue.get_next_story()
        if story:
            story.status = StoryStatus.IN_PROGRESS
            story.attempt_count += 1
            log_agent_action(
                self.name,
                "Starting story",
                f"{story.id} - {story.title} (attempt {story.attempt_count})",
            )
        return story

    def mark_story_completed(self, story_id: str) -> None:
        """Mark a story as completed.

        Args:
            story_id: ID of the story to mark complete.
        """
        for story in self.build_queue.stories:
            if story.id == story_id:
                story.status = StoryStatus.COMPLETED
                story.blockers.clear()
                log_agent_action(self.name, "Story completed", story_id)
                return
        log_agent_action(self.name, "Story not found", story_id)

    def mark_story_failed(self, story_id: str, reason: str) -> None:
        """Mark a story as failed.

        Args:
            story_id: ID of the story to mark failed.
            reason: Reason for the failure.
        """
        for story in self.build_queue.stories:
            if story.id == story_id:
                story.status = StoryStatus.FAILED
                story.failure_reasons.append(reason)
                log_agent_action(
                    self.name, "Story failed", f"{story_id}: {reason}"
                )
                return
        log_agent_action(self.name, "Story not found", story_id)

    def mark_story_blocked(self, story_id: str, blocker: str) -> None:
        """Mark a story as blocked.

        Args:
            story_id: ID of the story to mark blocked.
            blocker: Description of the blocker.
        """
        for story in self.build_queue.stories:
            if story.id == story_id:
                story.status = StoryStatus.BLOCKED
                story.blockers.append(blocker)
                log_agent_action(
                    self.name, "Story blocked", f"{story_id}: {blocker}"
                )
                return
        log_agent_action(self.name, "Story not found", story_id)

    def retry_story(self, story_id: str) -> bool:
        """Reset a failed/blocked story to pending for retry.

        Args:
            story_id: ID of the story to retry.

        Returns:
            True if story was found and reset, False otherwise.
        """
        for story in self.build_queue.stories:
            if story.id == story_id:
                if story.status in (StoryStatus.FAILED, StoryStatus.BLOCKED):
                    story.status = StoryStatus.PENDING
                    log_agent_action(self.name, "Story queued for retry", story_id)
                    return True
        return False

    def analyze_blocker(self, story_id: str, error_context: str) -> BlockerAnalysis:
        """Analyze a blocker and suggest solutions.

        Uses the LLM to analyze the error and suggest solutions.

        Args:
            story_id: ID of the blocked story.
            error_context: Error message or context describing the blocker.

        Returns:
            BlockerAnalysis with severity and suggested solutions.
        """
        # Find the story for context
        story_context = ""
        for story in self.build_queue.stories:
            if story.id == story_id:
                story_context = (
                    f"Story: {story.title}\n"
                    f"Description: {story.description}\n"
                    f"Acceptance Criteria: {', '.join(story.acceptance_criteria)}\n"
                    f"Previous attempts: {story.attempt_count}\n"
                )
                if story.failure_reasons:
                    story_context += f"Previous failures: {'; '.join(story.failure_reasons)}\n"
                break

        analysis_prompt = f"""{story_context}
Current Error/Blocker:
{error_context}

Analyze this blocker and respond with:
SEVERITY: [low/medium/high/critical]
REQUIRES_HUMAN: [yes/no]
SOLUTIONS:
1. [first solution]
2. [second solution]
3. [third solution if applicable]

Be specific and actionable in your solutions."""

        response = self.chat(analysis_prompt)

        # Parse response
        severity = "medium"
        requires_human = False
        solutions: list[str] = []

        lines = response.strip().split("\n")
        in_solutions = False

        for line in lines:
            line = line.strip()
            if line.upper().startswith("SEVERITY:"):
                sev_value = line.split(":", 1)[1].strip().lower()
                if sev_value in ("low", "medium", "high", "critical"):
                    severity = sev_value
            elif line.upper().startswith("REQUIRES_HUMAN:"):
                human_value = line.split(":", 1)[1].strip().lower()
                requires_human = human_value in ("yes", "true", "1")
            elif line.upper().startswith("SOLUTIONS:"):
                in_solutions = True
            elif in_solutions and line:
                # Strip leading numbers and punctuation
                solution = line.lstrip("0123456789.-) ").strip()
                if solution:
                    solutions.append(solution)

        analysis = BlockerAnalysis(
            blocker=error_context,
            severity=severity,
            suggested_solutions=solutions or ["Review error manually"],
            requires_human_intervention=requires_human,
        )

        log_agent_decision(
            self.name,
            f"Blocker analyzed: {severity} severity",
            f"Solutions: {len(solutions)}, Needs human: {requires_human}",
        )

        return analysis

    def get_status_report(self) -> str:
        """Generate a status report for the build.

        Returns:
            Formatted status report string.
        """
        summary = self.build_queue.get_summary()

        # Build report
        lines = [
            "=== Build Status Report ===",
            f"Total Stories: {summary['total']}",
            f"  ✓ Completed: {summary['completed']}",
            f"  ⏳ Pending: {summary['pending']}",
            f"  🔄 In Progress: {summary['in_progress']}",
            f"  ⚠️  Blocked: {summary['blocked']}",
            f"  ✗ Failed: {summary['failed']}",
        ]

        # Add blocked stories
        blocked = [s for s in self.build_queue.stories if s.status == StoryStatus.BLOCKED]
        if blocked:
            lines.append("\nBlocked Stories:")
            for story in blocked:
                lines.append(f"  - {story.id}: {', '.join(story.blockers)}")

        # Add failed stories
        failed = [s for s in self.build_queue.stories if s.status == StoryStatus.FAILED]
        if failed:
            lines.append("\nFailed Stories:")
            for story in failed:
                lines.append(f"  - {story.id}: {story.failure_reasons[-1] if story.failure_reasons else 'Unknown'}")

        return "\n".join(lines)

    def should_continue_build(self, max_retries: int = 3) -> bool:
        """Determine if the build should continue.

        Args:
            max_retries: Maximum retry attempts per story before giving up.

        Returns:
            True if there are actionable stories remaining.
        """
        for story in self.build_queue.stories:
            if story.status == StoryStatus.PENDING:
                return True
            if (
                story.status in (StoryStatus.FAILED, StoryStatus.BLOCKED)
                and story.attempt_count < max_retries
            ):
                # Reset for retry
                story.status = StoryStatus.PENDING
                return True
        return False

    def get_build_summary(self) -> dict[str, Any]:
        """Get a machine-readable build summary.

        Returns:
            Dict with build statistics and story states.
        """
        return {
            "summary": self.build_queue.get_summary(),
            "stories": [s.to_dict() for s in self.build_queue.stories],
        }

    def reset(self) -> None:
        """Reset the Scrum Master state."""
        self.build_queue = BuildQueue()
        self.clear_history()
        log_agent_action(self.name, "State reset", "Build queue cleared")
