"""Story Quality Checker Workflow for MAT.

This module provides a workflow that validates user stories before building,
ensuring they are properly sized, have specific acceptance criteria, and are
ordered correctly by dependencies.
"""

from dataclasses import dataclass, field
from typing import Any

from agents.base import BaseAgent
from llm.client import OllamaClient
from utils.logger import get_logger, log_agent_action


@dataclass
class QualityIssue:
    """A quality issue found in a user story.

    Attributes:
        story_id: ID of the story with the issue.
        issue_type: Type of issue (length, criteria, dependency, scope).
        description: Human-readable description of the issue.
        suggestion: Suggested fix for the issue.
    """

    story_id: str
    issue_type: str
    description: str
    suggestion: str

    def to_dict(self) -> dict[str, str]:
        """Convert issue to dictionary format."""
        return {
            "story_id": self.story_id,
            "issue_type": self.issue_type,
            "description": self.description,
            "suggestion": self.suggestion,
        }


@dataclass
class StorySpec:
    """A user story specification for quality checking.

    Attributes:
        id: Unique story identifier (e.g., US-001).
        title: Short story title.
        description: User story description.
        acceptance_criteria: List of acceptance criteria.
        priority: Story priority/order.
    """

    id: str
    title: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    priority: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StorySpec":
        """Create StorySpec from dictionary.

        Args:
            data: Dictionary with story data.

        Returns:
            StorySpec instance.
        """
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptanceCriteria", data.get("acceptance_criteria", [])),
            priority=data.get("priority", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "acceptanceCriteria": self.acceptance_criteria,
            "priority": self.priority,
        }

    def get_description_line_count(self) -> int:
        """Get the number of lines in the description."""
        return len([line for line in self.description.split("\n") if line.strip()])


@dataclass
class QualityReport:
    """Report from story quality check.

    Attributes:
        stories: List of checked stories.
        issues: List of quality issues found.
        fixed_stories: Stories after automatic fixes applied.
    """

    stories: list[StorySpec] = field(default_factory=list)
    issues: list[QualityIssue] = field(default_factory=list)
    fixed_stories: list[StorySpec] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """Check if any issues were found."""
        return len(self.issues) > 0

    @property
    def issue_count(self) -> int:
        """Get total number of issues."""
        return len(self.issues)

    def get_issues_by_type(self, issue_type: str) -> list[QualityIssue]:
        """Get issues of a specific type."""
        return [i for i in self.issues if i.issue_type == issue_type]

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = [
            "# Story Quality Report",
            "",
            f"**Total Stories:** {len(self.stories)}",
            f"**Issues Found:** {len(self.issues)}",
            "",
        ]

        if not self.issues:
            lines.append("✓ All stories pass quality checks.")
            return "\n".join(lines)

        lines.append("## Issues")
        lines.append("")

        # Group issues by type
        issue_types = sorted(set(i.issue_type for i in self.issues))
        for issue_type in issue_types:
            type_issues = self.get_issues_by_type(issue_type)
            lines.append(f"### {issue_type.title()} Issues ({len(type_issues)})")
            lines.append("")
            for issue in type_issues:
                lines.append(f"- **{issue.story_id}**: {issue.description}")
                lines.append(f"  - Suggestion: {issue.suggestion}")
            lines.append("")

        return "\n".join(lines)


# Maximum description length (in lines)
MAX_DESCRIPTION_LINES = 2

# Minimum acceptance criteria count
MIN_CRITERIA_COUNT = 2

# System prompt for the quality checker LLM
QUALITY_CHECKER_SYSTEM_PROMPT = """You are a user story quality analyst. Your job is to:
1. Identify stories that are too large or complex
2. Suggest how to split large stories into smaller ones
3. Identify missing or vague acceptance criteria
4. Detect dependency ordering issues

Be specific and actionable in your analysis."""


SPLIT_STORY_PROMPT = """Analyze this user story and split it into smaller, focused stories.

Original Story:
ID: {story_id}
Title: {title}
Description: {description}
Acceptance Criteria:
{criteria}

The story is too large because: {reason}

Split this into 2-4 smaller stories. Each story should:
- Be completable in one coding session
- Have a clear, single focus
- Keep related criteria together
- Include "Typecheck passes" in criteria

Format your response EXACTLY like this:
---
ID: {story_id}-A
TITLE: [short title]
DESCRIPTION: [1-2 line description]
CRITERIA:
- [criterion 1]
- [criterion 2]
- Typecheck passes
---
ID: {story_id}-B
TITLE: [short title]
DESCRIPTION: [1-2 line description]
CRITERIA:
- [criterion 1]
- [criterion 2]
- Typecheck passes
---"""


DEPENDENCY_CHECK_PROMPT = """Analyze these user stories for dependency ordering issues.

Stories:
{stories}

Check if stories are ordered correctly by dependencies. For example:
- Database setup should come before backend logic
- Backend API should come before frontend components
- Core utilities should come before features that use them

List any stories that should be reordered. Format:
REORDER: [story_id] should come BEFORE [other_story_id] because [reason]

If ordering is correct, respond with:
ORDER_OK: Stories are correctly ordered by dependencies."""


@dataclass
class StoryQualityChecker:
    """Workflow for validating and fixing user story quality.

    This workflow checks that user stories are:
    - Properly sized (1-2 lines max description)
    - Have specific acceptance criteria
    - Are ordered by dependencies
    - Can be automatically split if too large

    Attributes:
        client: LLM client for analysis that requires reasoning.
        stories: List of stories to check.
        report: The quality check report.
    """

    client: OllamaClient = field(default_factory=OllamaClient)
    stories: list[StorySpec] = field(default_factory=list)
    report: QualityReport = field(default_factory=QualityReport)

    def load_stories(self, stories_data: list[dict[str, Any]]) -> None:
        """Load stories from dictionary format.

        Args:
            stories_data: List of story dictionaries.
        """
        self.stories = [StorySpec.from_dict(s) for s in stories_data]
        log_agent_action("StoryQuality", "Loaded stories", str(len(self.stories)))

    def _check_story_length(self, story: StorySpec) -> QualityIssue | None:
        """Check if story description is within acceptable length.

        Args:
            story: The story to check.

        Returns:
            QualityIssue if too long, None otherwise.
        """
        line_count = story.get_description_line_count()

        if line_count > MAX_DESCRIPTION_LINES:
            return QualityIssue(
                story_id=story.id,
                issue_type="length",
                description=f"Description is {line_count} lines (max is {MAX_DESCRIPTION_LINES})",
                suggestion="Split into multiple smaller stories or condense the description",
            )
        return None

    def _check_acceptance_criteria(self, story: StorySpec) -> list[QualityIssue]:
        """Check if story has sufficient acceptance criteria.

        Args:
            story: The story to check.

        Returns:
            List of QualityIssues found.
        """
        issues: list[QualityIssue] = []

        # Check minimum criteria count
        if len(story.acceptance_criteria) < MIN_CRITERIA_COUNT:
            issues.append(QualityIssue(
                story_id=story.id,
                issue_type="criteria",
                description=f"Only {len(story.acceptance_criteria)} acceptance criteria (minimum is {MIN_CRITERIA_COUNT})",
                suggestion="Add more specific, verifiable acceptance criteria",
            ))

        # Check for typecheck criterion
        has_typecheck = any(
            "typecheck" in c.lower() or "type check" in c.lower()
            for c in story.acceptance_criteria
        )
        if not has_typecheck:
            issues.append(QualityIssue(
                story_id=story.id,
                issue_type="criteria",
                description="Missing 'Typecheck passes' criterion",
                suggestion="Add 'Typecheck passes' to acceptance criteria",
            ))

        # Check for vague criteria
        vague_words = ["should work", "must be good", "should be nice", "etc", "and more"]
        for criterion in story.acceptance_criteria:
            criterion_lower = criterion.lower()
            for vague in vague_words:
                if vague in criterion_lower:
                    issues.append(QualityIssue(
                        story_id=story.id,
                        issue_type="criteria",
                        description=f"Vague criterion: '{criterion}'",
                        suggestion="Make criterion specific and verifiable",
                    ))
                    break

        return issues

    def _check_story_scope(self, story: StorySpec) -> QualityIssue | None:
        """Check if story scope is appropriate for single session.

        Args:
            story: The story to check.

        Returns:
            QualityIssue if scope is too large, None otherwise.
        """
        # Heuristic: too many criteria suggests too large scope
        if len(story.acceptance_criteria) > 7:
            return QualityIssue(
                story_id=story.id,
                issue_type="scope",
                description=f"Story has {len(story.acceptance_criteria)} acceptance criteria (may be too large)",
                suggestion="Consider splitting into multiple focused stories",
            )
        return None

    def check_all_stories(self) -> QualityReport:
        """Run all quality checks on loaded stories.

        Returns:
            QualityReport with all issues found.
        """
        log_agent_action("StoryQuality", "Running quality checks")

        self.report = QualityReport(stories=self.stories.copy())
        issues: list[QualityIssue] = []

        for story in self.stories:
            # Check length
            length_issue = self._check_story_length(story)
            if length_issue:
                issues.append(length_issue)

            # Check criteria
            criteria_issues = self._check_acceptance_criteria(story)
            issues.extend(criteria_issues)

            # Check scope
            scope_issue = self._check_story_scope(story)
            if scope_issue:
                issues.append(scope_issue)

        self.report.issues = issues
        log_agent_action(
            "StoryQuality",
            "Quality check complete",
            f"{len(issues)} issues found",
        )

        return self.report

    def check_dependency_order(self) -> list[QualityIssue]:
        """Check if stories are ordered correctly by dependencies.

        Uses LLM to analyze story dependencies and ordering.

        Returns:
            List of dependency ordering issues.
        """
        if not self.stories:
            return []

        log_agent_action("StoryQuality", "Checking dependency order")

        # Format stories for LLM
        stories_text = "\n\n".join(
            f"Priority {s.priority}: {s.id} - {s.title}\n  Description: {s.description}"
            for s in sorted(self.stories, key=lambda x: x.priority)
        )

        prompt = DEPENDENCY_CHECK_PROMPT.format(stories=stories_text)

        # Create temporary agent for LLM interaction
        agent = BaseAgent(
            name="DependencyChecker",
            role="Checks story dependency ordering",
            system_prompt=QUALITY_CHECKER_SYSTEM_PROMPT,
            client=self.client,
        )

        response = agent.chat(prompt)

        # Parse response for reorder suggestions
        issues: list[QualityIssue] = []

        if "ORDER_OK" in response:
            log_agent_action("StoryQuality", "Dependency order OK")
            return issues

        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("REORDER:"):
                # Extract the reorder suggestion
                suggestion = line.replace("REORDER:", "").strip()
                # Try to extract story ID
                parts = suggestion.split()
                story_id = parts[0] if parts else "unknown"

                issues.append(QualityIssue(
                    story_id=story_id,
                    issue_type="dependency",
                    description=suggestion,
                    suggestion="Reorder stories to satisfy dependencies",
                ))

        if issues:
            self.report.issues.extend(issues)

        log_agent_action(
            "StoryQuality",
            "Dependency check complete",
            f"{len(issues)} ordering issues",
        )

        return issues

    def _parse_split_response(self, response: str, original_id: str) -> list[StorySpec]:
        """Parse LLM response for split stories.

        Args:
            response: Raw LLM response with split story format.
            original_id: Original story ID for reference.

        Returns:
            List of new StorySpec objects.
        """
        stories: list[StorySpec] = []
        logger = get_logger()

        current_story: dict[str, Any] = {}
        current_criteria: list[str] = []

        def save_current() -> None:
            nonlocal current_story, current_criteria
            if current_story.get("id"):
                current_story["acceptance_criteria"] = current_criteria.copy()
                stories.append(StorySpec(
                    id=current_story.get("id", ""),
                    title=current_story.get("title", ""),
                    description=current_story.get("description", ""),
                    acceptance_criteria=current_story.get("acceptance_criteria", []),
                ))
            current_story = {}
            current_criteria = []

        for line in response.split("\n"):
            line_stripped = line.strip()

            if line_stripped == "---":
                save_current()
                continue

            if line_stripped.startswith("ID:"):
                if current_story.get("id"):
                    save_current()
                current_story["id"] = line_stripped.replace("ID:", "").strip()

            elif line_stripped.startswith("TITLE:"):
                current_story["title"] = line_stripped.replace("TITLE:", "").strip()

            elif line_stripped.startswith("DESCRIPTION:"):
                current_story["description"] = line_stripped.replace("DESCRIPTION:", "").strip()

            elif line_stripped == "CRITERIA:":
                current_criteria = []

            elif line_stripped.startswith("-") and current_story.get("id"):
                current_criteria.append(line_stripped[1:].strip())

        # Save final story
        save_current()

        logger.debug(f"Parsed {len(stories)} split stories from response")
        return stories

    def split_story(self, story_id: str, reason: str = "too large") -> list[StorySpec]:
        """Split a large story into smaller stories using LLM.

        Args:
            story_id: ID of the story to split.
            reason: Reason for splitting (for context).

        Returns:
            List of new smaller stories.
        """
        # Find the story
        story = next((s for s in self.stories if s.id == story_id), None)
        if not story:
            log_agent_action("StoryQuality", "Story not found", story_id)
            return []

        log_agent_action("StoryQuality", "Splitting story", story_id)

        # Format criteria for prompt
        criteria_text = "\n".join(f"- {c}" for c in story.acceptance_criteria)

        prompt = SPLIT_STORY_PROMPT.format(
            story_id=story.id,
            title=story.title,
            description=story.description,
            criteria=criteria_text,
            reason=reason,
        )

        # Create temporary agent for LLM interaction
        agent = BaseAgent(
            name="StorySplitter",
            role="Splits large stories into smaller ones",
            system_prompt=QUALITY_CHECKER_SYSTEM_PROMPT,
            client=self.client,
        )

        response = agent.chat(prompt)
        new_stories = self._parse_split_response(response, story.id)

        if new_stories:
            log_agent_action(
                "StoryQuality",
                "Story split complete",
                f"{story_id} → {len(new_stories)} stories",
            )

        return new_stories

    def auto_fix_stories(self) -> list[StorySpec]:
        """Automatically fix common story issues.

        This method:
        - Adds missing 'Typecheck passes' criterion
        - Splits stories that are too large
        - Returns the fixed list of stories

        Returns:
            List of fixed stories.
        """
        log_agent_action("StoryQuality", "Auto-fixing story issues")

        fixed_stories: list[StorySpec] = []
        stories_to_split: list[str] = []

        for story in self.stories:
            # Check if story needs splitting
            needs_split = (
                story.get_description_line_count() > MAX_DESCRIPTION_LINES or
                len(story.acceptance_criteria) > 7
            )

            if needs_split:
                stories_to_split.append(story.id)
                continue

            # Fix missing typecheck criterion
            has_typecheck = any(
                "typecheck" in c.lower() or "type check" in c.lower()
                for c in story.acceptance_criteria
            )
            if not has_typecheck:
                story.acceptance_criteria.append("Typecheck passes")

            fixed_stories.append(story)

        # Split large stories
        for story_id in stories_to_split:
            split_stories = self.split_story(story_id)
            if split_stories:
                fixed_stories.extend(split_stories)
            else:
                # If splitting failed, keep original
                original = next((s for s in self.stories if s.id == story_id), None)
                if original:
                    fixed_stories.append(original)

        # Re-assign priorities based on order
        for i, story in enumerate(fixed_stories):
            story.priority = i + 1

        self.report.fixed_stories = fixed_stories

        log_agent_action(
            "StoryQuality",
            "Auto-fix complete",
            f"{len(fixed_stories)} stories (was {len(self.stories)})",
        )

        return fixed_stories

    def get_fixed_stories_as_dicts(self) -> list[dict[str, Any]]:
        """Get fixed stories in dictionary format for prd.json.

        Returns:
            List of story dictionaries.
        """
        stories = self.report.fixed_stories or self.stories
        return [s.to_dict() for s in stories]

    def run_full_check(
        self,
        stories_data: list[dict[str, Any]],
        auto_fix: bool = True,
        check_dependencies: bool = True,
    ) -> QualityReport:
        """Run complete quality check workflow.

        Args:
            stories_data: List of story dictionaries.
            auto_fix: Whether to automatically fix issues.
            check_dependencies: Whether to check dependency ordering.

        Returns:
            QualityReport with results.
        """
        log_agent_action("StoryQuality", "Running full quality check")

        # Load stories
        self.load_stories(stories_data)

        # Run basic checks
        self.check_all_stories()

        # Check dependencies if requested
        if check_dependencies:
            self.check_dependency_order()

        # Auto-fix if requested
        if auto_fix:
            self.auto_fix_stories()

        log_agent_action(
            "StoryQuality",
            "Full check complete",
            f"{self.report.issue_count} issues, {len(self.report.fixed_stories)} fixed stories",
        )

        return self.report
