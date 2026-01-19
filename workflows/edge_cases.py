"""Edge Case Analyzer Workflow for MAT.

This module provides a workflow that analyzes PRDs for potential edge cases
and adds them to acceptance criteria to ensure robust implementations.
"""

from dataclasses import dataclass, field
from typing import Any

from agents.base import BaseAgent
from llm.client import OllamaClient
from utils.logger import get_logger, log_agent_action


@dataclass
class EdgeCase:
    """A detected edge case.

    Attributes:
        story_id: ID of the story the edge case applies to.
        category: Type of edge case (input, state, error, security).
        description: Human-readable description of the edge case.
        criterion: Suggested acceptance criterion to add.
        severity: Impact level (low, medium, high).
    """

    story_id: str
    category: str
    description: str
    criterion: str
    severity: str = "medium"

    def to_dict(self) -> dict[str, str]:
        """Convert edge case to dictionary format."""
        return {
            "story_id": self.story_id,
            "category": self.category,
            "description": self.description,
            "criterion": self.criterion,
            "severity": self.severity,
        }


@dataclass
class EdgeCaseReport:
    """Report from edge case analysis.

    Attributes:
        story_count: Number of stories analyzed.
        edge_cases: List of detected edge cases.
        updated_criteria: Map of story_id to added criteria.
    """

    story_count: int = 0
    edge_cases: list[EdgeCase] = field(default_factory=list)
    updated_criteria: dict[str, list[str]] = field(default_factory=dict)

    @property
    def edge_case_count(self) -> int:
        """Get total number of edge cases found."""
        return len(self.edge_cases)

    def get_by_category(self, category: str) -> list[EdgeCase]:
        """Get edge cases of a specific category."""
        return [ec for ec in self.edge_cases if ec.category == category]

    def get_by_story(self, story_id: str) -> list[EdgeCase]:
        """Get edge cases for a specific story."""
        return [ec for ec in self.edge_cases if ec.story_id == story_id]

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = [
            "# Edge Case Analysis Report",
            "",
            f"**Stories Analyzed:** {self.story_count}",
            f"**Edge Cases Found:** {self.edge_case_count}",
            "",
        ]

        if not self.edge_cases:
            lines.append("✓ No significant edge cases identified.")
            return "\n".join(lines)

        # Group by category
        categories = sorted({ec.category for ec in self.edge_cases})
        for category in categories:
            category_cases = self.get_by_category(category)
            lines.append(f"## {category.title()} Edge Cases ({len(category_cases)})")
            lines.append("")

            for ec in category_cases:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    ec.severity, "⚪"
                )
                lines.append(f"### {severity_icon} {ec.story_id}: {ec.description}")
                lines.append(f"- **Suggested criterion:** {ec.criterion}")
                lines.append("")

        # Summary of updated criteria
        if self.updated_criteria:
            lines.append("## Updated Stories")
            lines.append("")
            for story_id, criteria in self.updated_criteria.items():
                lines.append(f"### {story_id}")
                lines.append("Added criteria:")
                for criterion in criteria:
                    lines.append(f"- {criterion}")
                lines.append("")

        return "\n".join(lines)


# Category constants
CATEGORY_INPUT = "input"
CATEGORY_STATE = "state"
CATEGORY_ERROR = "error"
CATEGORY_SECURITY = "security"

# System prompt for the edge case analyzer LLM
EDGE_CASE_SYSTEM_PROMPT = """You are an edge case analyst. Your job is to identify potential \
edge cases that could cause issues in software implementations.

Focus on:
1. Input edge cases: empty values, null, boundary values, invalid formats, special characters
2. State edge cases: race conditions, concurrent access, state transitions, timing issues
3. Error handling: network failures, timeouts, validation errors, external service failures
4. Security: input validation, injection, unauthorized access, data exposure

Be specific and actionable. For each edge case, suggest a concrete acceptance criterion."""


INPUT_EDGE_CASE_PROMPT = """Analyze this user story for INPUT edge cases.

Story ID: {story_id}
Title: {title}
Description: {description}
Current Acceptance Criteria:
{criteria}

Identify input edge cases such as:
- Empty or null values
- Boundary values (min/max, zero, negative)
- Invalid formats (wrong type, malformed data)
- Special characters that could cause issues
- Unicode and encoding issues
- Very long or very short inputs

For each edge case found, respond in this EXACT format (one per line):
EDGE: [description] | CRITERION: [acceptance criterion] | SEVERITY: [low/medium/high]

If no significant input edge cases, respond:
NONE_FOUND: No significant input edge cases for this story.

Only include edge cases that are relevant to this specific story."""


STATE_EDGE_CASE_PROMPT = """Analyze this user story for STATE edge cases.

Story ID: {story_id}
Title: {title}
Description: {description}
Current Acceptance Criteria:
{criteria}

Identify state edge cases such as:
- Race conditions when multiple users/processes access same resource
- Concurrent modifications to shared state
- Invalid state transitions (e.g., deleting already-deleted item)
- Stale data issues
- Interrupted operations (partial completion)
- Order-dependent operations
- Session/authentication state issues

For each edge case found, respond in this EXACT format (one per line):
EDGE: [description] | CRITERION: [acceptance criterion] | SEVERITY: [low/medium/high]

If no significant state edge cases, respond:
NONE_FOUND: No significant state edge cases for this story.

Only include edge cases that are relevant to this specific story."""


ERROR_EDGE_CASE_PROMPT = """Analyze this user story for ERROR HANDLING edge cases.

Story ID: {story_id}
Title: {title}
Description: {description}
Current Acceptance Criteria:
{criteria}

Identify error handling edge cases such as:
- Network failures (connection refused, timeout)
- External service unavailability
- Validation errors and user feedback
- File system errors (permission denied, disk full)
- Database errors (constraint violations, connection lost)
- Memory/resource exhaustion
- Graceful degradation scenarios

For each edge case found, respond in this EXACT format (one per line):
EDGE: [description] | CRITERION: [acceptance criterion] | SEVERITY: [low/medium/high]

If no significant error edge cases, respond:
NONE_FOUND: No significant error handling edge cases for this story.

Only include edge cases that are relevant to this specific story."""


SECURITY_EDGE_CASE_PROMPT = """Analyze this user story for SECURITY edge cases.

Story ID: {story_id}
Title: {title}
Description: {description}
Current Acceptance Criteria:
{criteria}

Identify security edge cases such as:
- Input injection (SQL, command, XSS)
- Authentication bypass
- Authorization failures (accessing others' data)
- Path traversal attacks
- Sensitive data exposure in logs/errors
- Missing rate limiting
- Insecure defaults

For each edge case found, respond in this EXACT format (one per line):
EDGE: [description] | CRITERION: [acceptance criterion] | SEVERITY: [low/medium/high]

If no significant security edge cases, respond:
NONE_FOUND: No significant security edge cases for this story.

Only include edge cases that are relevant to this specific story."""


@dataclass
class EdgeCaseAnalyzer:
    """Workflow for analyzing PRDs for edge cases.

    This workflow analyzes user stories to identify potential edge cases
    that should be addressed in the implementation.

    Attributes:
        client: LLM client for analysis.
        stories: List of stories to analyze (dict format).
        report: The edge case analysis report.
    """

    client: OllamaClient = field(default_factory=OllamaClient)
    stories: list[dict[str, Any]] = field(default_factory=list)
    report: EdgeCaseReport = field(default_factory=EdgeCaseReport)

    def load_stories(self, stories_data: list[dict[str, Any]]) -> None:
        """Load stories from dictionary format.

        Args:
            stories_data: List of story dictionaries.
        """
        self.stories = stories_data
        log_agent_action("EdgeCases", "Loaded stories", str(len(self.stories)))

    def _parse_edge_cases(
        self, response: str, story_id: str, category: str
    ) -> list[EdgeCase]:
        """Parse LLM response for edge cases.

        Args:
            response: Raw LLM response.
            story_id: ID of the story being analyzed.
            category: Edge case category.

        Returns:
            List of parsed EdgeCase objects.
        """
        edge_cases: list[EdgeCase] = []
        logger = get_logger()

        for line in response.split("\n"):
            line = line.strip()

            if line.startswith("NONE_FOUND:"):
                return []

            if line.startswith("EDGE:"):
                try:
                    # Parse format: EDGE: [desc] | CRITERION: [crit] | SEVERITY: [sev]
                    parts = line.replace("EDGE:", "").split("|")
                    if len(parts) >= 2:
                        description = parts[0].strip()

                        criterion = ""
                        severity = "medium"

                        for part in parts[1:]:
                            part = part.strip()
                            if part.startswith("CRITERION:"):
                                criterion = part.replace("CRITERION:", "").strip()
                            elif part.startswith("SEVERITY:"):
                                sev = part.replace("SEVERITY:", "").strip().lower()
                                if sev in ("low", "medium", "high"):
                                    severity = sev

                        if description and criterion:
                            edge_cases.append(EdgeCase(
                                story_id=story_id,
                                category=category,
                                description=description,
                                criterion=criterion,
                                severity=severity,
                            ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse edge case line: {line}, error: {e}")
                    continue

        return edge_cases

    def _analyze_category(
        self,
        story: dict[str, Any],
        category: str,
        prompt_template: str,
    ) -> list[EdgeCase]:
        """Analyze a story for edge cases in a specific category.

        Args:
            story: Story dictionary.
            category: Edge case category.
            prompt_template: Prompt template for this category.

        Returns:
            List of edge cases found.
        """
        story_id = story.get("id", "unknown")
        title = story.get("title", "")
        description = story.get("description", "")
        criteria = story.get("acceptanceCriteria", story.get("acceptance_criteria", []))
        criteria_text = "\n".join(f"- {c}" for c in criteria)

        prompt = prompt_template.format(
            story_id=story_id,
            title=title,
            description=description,
            criteria=criteria_text or "None specified",
        )

        # Create temporary agent for LLM interaction
        agent = BaseAgent(
            name="EdgeCaseAnalyzer",
            role=f"Analyzes {category} edge cases",
            system_prompt=EDGE_CASE_SYSTEM_PROMPT,
            client=self.client,
        )

        response = agent.chat(prompt)
        return self._parse_edge_cases(response, story_id, category)

    def analyze_input_edge_cases(
        self, story: dict[str, Any]
    ) -> list[EdgeCase]:
        """Analyze a story for input edge cases.

        Args:
            story: Story dictionary.

        Returns:
            List of input edge cases found.
        """
        return self._analyze_category(story, CATEGORY_INPUT, INPUT_EDGE_CASE_PROMPT)

    def analyze_state_edge_cases(
        self, story: dict[str, Any]
    ) -> list[EdgeCase]:
        """Analyze a story for state edge cases.

        Args:
            story: Story dictionary.

        Returns:
            List of state edge cases found.
        """
        return self._analyze_category(story, CATEGORY_STATE, STATE_EDGE_CASE_PROMPT)

    def analyze_error_edge_cases(
        self, story: dict[str, Any]
    ) -> list[EdgeCase]:
        """Analyze a story for error handling edge cases.

        Args:
            story: Story dictionary.

        Returns:
            List of error edge cases found.
        """
        return self._analyze_category(story, CATEGORY_ERROR, ERROR_EDGE_CASE_PROMPT)

    def analyze_security_edge_cases(
        self, story: dict[str, Any]
    ) -> list[EdgeCase]:
        """Analyze a story for security edge cases.

        Args:
            story: Story dictionary.

        Returns:
            List of security edge cases found.
        """
        return self._analyze_category(story, CATEGORY_SECURITY, SECURITY_EDGE_CASE_PROMPT)

    def analyze_story(self, story: dict[str, Any]) -> list[EdgeCase]:
        """Analyze a single story for all types of edge cases.

        Args:
            story: Story dictionary.

        Returns:
            List of all edge cases found.
        """
        story_id = story.get("id", "unknown")
        log_agent_action("EdgeCases", "Analyzing story", story_id)

        all_edge_cases: list[EdgeCase] = []

        # Analyze each category
        all_edge_cases.extend(self.analyze_input_edge_cases(story))
        all_edge_cases.extend(self.analyze_state_edge_cases(story))
        all_edge_cases.extend(self.analyze_error_edge_cases(story))
        all_edge_cases.extend(self.analyze_security_edge_cases(story))

        log_agent_action(
            "EdgeCases",
            "Story analysis complete",
            f"{story_id}: {len(all_edge_cases)} edge cases",
        )

        return all_edge_cases

    def analyze_all_stories(self) -> EdgeCaseReport:
        """Analyze all loaded stories for edge cases.

        Returns:
            EdgeCaseReport with all findings.
        """
        log_agent_action("EdgeCases", "Analyzing all stories")

        self.report = EdgeCaseReport(story_count=len(self.stories))
        all_edge_cases: list[EdgeCase] = []

        for story in self.stories:
            story_edge_cases = self.analyze_story(story)
            all_edge_cases.extend(story_edge_cases)

        self.report.edge_cases = all_edge_cases

        log_agent_action(
            "EdgeCases",
            "Full analysis complete",
            f"{self.report.edge_case_count} edge cases found",
        )

        return self.report

    def add_edge_cases_to_criteria(
        self,
        max_per_story: int = 3,
        min_severity: str = "medium",
    ) -> list[dict[str, Any]]:
        """Add edge case criteria to stories.

        Modifies the loaded stories by adding edge case acceptance criteria.

        Args:
            max_per_story: Maximum edge cases to add per story.
            min_severity: Minimum severity to include (low, medium, high).

        Returns:
            Updated list of story dictionaries.
        """
        log_agent_action("EdgeCases", "Adding edge cases to acceptance criteria")

        severity_order = {"low": 0, "medium": 1, "high": 2}
        min_sev_value = severity_order.get(min_severity, 1)

        self.report.updated_criteria = {}

        for story in self.stories:
            story_id = story.get("id", "")

            # Get edge cases for this story
            story_edge_cases = self.report.get_by_story(story_id)

            # Filter by severity and sort by severity (highest first)
            filtered = [
                ec for ec in story_edge_cases
                if severity_order.get(ec.severity, 1) >= min_sev_value
            ]
            filtered.sort(
                key=lambda ec: severity_order.get(ec.severity, 1),
                reverse=True,
            )

            # Take top N edge cases
            to_add = filtered[:max_per_story]

            if to_add:
                # Get existing criteria
                criteria_key = (
                    "acceptanceCriteria"
                    if "acceptanceCriteria" in story
                    else "acceptance_criteria"
                )
                existing = story.get(criteria_key, [])

                # Add new criteria (avoid duplicates)
                added_criteria: list[str] = []
                for ec in to_add:
                    if ec.criterion not in existing:
                        existing.append(ec.criterion)
                        added_criteria.append(ec.criterion)

                story[criteria_key] = existing
                if added_criteria:
                    self.report.updated_criteria[story_id] = added_criteria

        log_agent_action(
            "EdgeCases",
            "Criteria update complete",
            f"{len(self.report.updated_criteria)} stories updated",
        )

        return self.stories

    def get_high_severity_cases(self) -> list[EdgeCase]:
        """Get all high severity edge cases.

        Returns:
            List of high severity edge cases.
        """
        return [ec for ec in self.report.edge_cases if ec.severity == "high"]

    def run_full_analysis(
        self,
        stories_data: list[dict[str, Any]],
        add_to_criteria: bool = True,
        max_per_story: int = 3,
        min_severity: str = "medium",
    ) -> EdgeCaseReport:
        """Run complete edge case analysis workflow.

        Args:
            stories_data: List of story dictionaries.
            add_to_criteria: Whether to add edge cases to acceptance criteria.
            max_per_story: Maximum edge cases to add per story.
            min_severity: Minimum severity for adding to criteria.

        Returns:
            EdgeCaseReport with results.
        """
        log_agent_action("EdgeCases", "Running full edge case analysis")

        # Load stories
        self.load_stories(stories_data)

        # Analyze all stories
        self.analyze_all_stories()

        # Add to criteria if requested
        if add_to_criteria:
            self.add_edge_cases_to_criteria(
                max_per_story=max_per_story,
                min_severity=min_severity,
            )

        log_agent_action(
            "EdgeCases",
            "Full analysis workflow complete",
            f"{self.report.edge_case_count} edge cases, "
            f"{len(self.report.updated_criteria)} stories updated",
        )

        return self.report

    def get_updated_stories(self) -> list[dict[str, Any]]:
        """Get stories with added edge case criteria.

        Returns:
            List of story dictionaries with updated criteria.
        """
        return self.stories
