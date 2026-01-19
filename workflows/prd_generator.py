"""PRD Generation Workflow for MAT.

This module provides a workflow that uses the ProductManagerAgent to conduct
discovery interviews and generate structured Product Requirements Documents (PRDs).
"""

from dataclasses import dataclass, field
from pathlib import Path

from agents.pm import DiscoveryPhase, ProductManagerAgent
from utils.file_ops import write_file
from utils.logger import get_logger, log_agent_action


@dataclass
class UserStorySpec:
    """A user story specification for the PRD."""

    id: str
    title: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert user story to markdown format."""
        lines = [
            f"### {self.id}: {self.title}",
            "",
            f"**As a** user, **I want** {self.description}",
            "",
            "**Acceptance Criteria:**",
        ]
        for criterion in self.acceptance_criteria:
            lines.append(f"- {criterion}")
        return "\n".join(lines)


@dataclass
class PRDDocument:
    """A Product Requirements Document.

    Attributes:
        project_name: Name of the project.
        overview: High-level project overview.
        goals: List of project goals.
        user_stories: List of user story specifications.
        requirements: Technical and functional requirements.
        non_goals: What is explicitly out of scope.
    """

    project_name: str = ""
    overview: str = ""
    goals: list[str] = field(default_factory=list)
    user_stories: list[UserStorySpec] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert PRD to markdown format.

        Returns:
            Complete PRD as markdown string.
        """
        lines = [
            f"# Product Requirements Document: {self.project_name}",
            "",
            "## Overview",
            "",
            self.overview,
            "",
            "## Goals",
            "",
        ]

        for goal in self.goals:
            lines.append(f"- {goal}")

        lines.extend([
            "",
            "## User Stories",
            "",
        ])

        for story in self.user_stories:
            lines.append(story.to_markdown())
            lines.append("")

        lines.extend([
            "## Requirements",
            "",
        ])

        for req in self.requirements:
            lines.append(f"- {req}")

        lines.extend([
            "",
            "## Non-Goals (Out of Scope)",
            "",
        ])

        for non_goal in self.non_goals:
            lines.append(f"- {non_goal}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        """Convert PRD to dictionary format.

        Returns:
            Dictionary representation of the PRD.
        """
        return {
            "project_name": self.project_name,
            "overview": self.overview,
            "goals": self.goals,
            "user_stories": [
                {
                    "id": s.id,
                    "title": s.title,
                    "description": s.description,
                    "acceptance_criteria": s.acceptance_criteria,
                }
                for s in self.user_stories
            ],
            "requirements": self.requirements,
            "non_goals": self.non_goals,
        }


PRD_GENERATION_PROMPT = """Based on the discovery findings, generate a structured PRD.

Discovery Findings:
- Problem: {problem}
- Users: {users}
- Features: {features}
- Success Criteria: {success}
- Out of Scope: {scope}

Generate output in this EXACT format (use these markers):

PROJECT_NAME: [project name in 2-3 words]

OVERVIEW: [1-2 sentence overview of what this project does and why]

GOALS:
- [goal 1]
- [goal 2]
- [goal 3]

USER_STORIES:
---
ID: US-001
TITLE: [short title]
DESCRIPTION: [what the user wants to do]
CRITERIA:
- [criterion 1]
- [criterion 2]
- Typecheck passes
---
ID: US-002
TITLE: [short title]
DESCRIPTION: [what the user wants to do]
CRITERIA:
- [criterion 1]
- [criterion 2]
- Typecheck passes
---
[continue for each story, separated by ---]

REQUIREMENTS:
- [technical requirement 1]
- [technical requirement 2]

NON_GOALS:
- [out of scope item 1]
- [out of scope item 2]

Important:
- Generate 3-8 user stories based on the core features
- Each story should be small and focused
- Include "Typecheck passes" in every story's criteria
- Keep stories independent when possible
- Order stories by dependencies (foundation first)"""


@dataclass
class PRDGenerator:
    """Workflow for generating PRDs from discovery interviews.

    This workflow orchestrates the ProductManagerAgent to conduct discovery
    interviews, then generates a structured PRD from the findings.

    Attributes:
        pm_agent: The ProductManagerAgent instance.
        prd: The generated PRD document.
        output_path: Path where PRD will be saved.
    """

    pm_agent: ProductManagerAgent = field(default_factory=ProductManagerAgent)
    prd: PRDDocument = field(default_factory=PRDDocument)
    output_path: str = "tasks/prd.md"

    def start_discovery(self) -> str:
        """Start the discovery interview process.

        Returns:
            Opening message and first question from PM agent.
        """
        log_agent_action("PRDGenerator", "Starting discovery interview")
        return self.pm_agent.start_interview()

    def process_user_input(self, user_input: str) -> str:
        """Process user input during discovery.

        Args:
            user_input: The user's response to the current question.

        Returns:
            Next question, follow-up, or summary.
        """
        return self.pm_agent.process_response(user_input)

    def is_discovery_complete(self) -> bool:
        """Check if discovery interview is complete.

        Returns:
            True if all discovery phases are done.
        """
        return self.pm_agent.is_interview_complete()

    def get_discovery_findings(self) -> dict[str, str]:
        """Get the collected discovery findings.

        Returns:
            Dictionary with problem, users, features, success, scope.
        """
        return self.pm_agent.get_findings()

    def _parse_prd_response(self, response: str) -> PRDDocument:
        """Parse LLM response into PRDDocument.

        Args:
            response: Raw LLM response with PRD content.

        Returns:
            Parsed PRDDocument.
        """
        prd = PRDDocument()
        logger = get_logger()

        lines = response.split("\n")
        current_section = ""

        # Track current story being parsed
        story_id = ""
        story_title = ""
        story_description = ""
        story_criteria: list[str] = []
        stories: list[UserStorySpec] = []

        def save_current_story() -> None:
            """Save current story if valid and reset."""
            nonlocal story_id, story_title, story_description, story_criteria
            if story_id:
                stories.append(UserStorySpec(
                    id=story_id,
                    title=story_title,
                    description=story_description,
                    acceptance_criteria=story_criteria.copy(),
                ))
            story_id = ""
            story_title = ""
            story_description = ""
            story_criteria = []

        for line in lines:
            line_stripped = line.strip()

            # Detect section markers
            if line_stripped.startswith("PROJECT_NAME:"):
                prd.project_name = line_stripped.replace("PROJECT_NAME:", "").strip()
                continue

            if line_stripped.startswith("OVERVIEW:"):
                current_section = "overview"
                content = line_stripped.replace("OVERVIEW:", "").strip()
                if content:
                    prd.overview = content
                continue

            if line_stripped == "GOALS:":
                current_section = "goals"
                continue

            if line_stripped == "USER_STORIES:":
                current_section = "stories"
                continue

            if line_stripped == "REQUIREMENTS:":
                # Save any pending story before switching sections
                save_current_story()
                current_section = "requirements"
                continue

            if line_stripped == "NON_GOALS:":
                current_section = "non_goals"
                continue

            # Handle story separators
            if line_stripped == "---" and current_section == "stories":
                save_current_story()
                continue

            # Parse content based on current section
            if current_section == "overview" and line_stripped:
                if prd.overview:
                    prd.overview += " " + line_stripped
                else:
                    prd.overview = line_stripped

            elif current_section == "goals" and line_stripped.startswith("-"):
                prd.goals.append(line_stripped[1:].strip())

            elif current_section == "stories":
                if line_stripped.startswith("ID:"):
                    story_id = line_stripped.replace("ID:", "").strip()
                elif line_stripped.startswith("TITLE:"):
                    story_title = line_stripped.replace("TITLE:", "").strip()
                elif line_stripped.startswith("DESCRIPTION:"):
                    story_description = line_stripped.replace("DESCRIPTION:", "").strip()
                elif line_stripped == "CRITERIA:":
                    story_criteria = []
                elif line_stripped.startswith("-") and story_id:
                    story_criteria.append(line_stripped[1:].strip())

            elif current_section == "requirements" and line_stripped.startswith("-"):
                prd.requirements.append(line_stripped[1:].strip())

            elif current_section == "non_goals" and line_stripped.startswith("-"):
                prd.non_goals.append(line_stripped[1:].strip())

        # Save any final story
        save_current_story()

        # Set parsed stories
        prd.user_stories = stories

        logger.debug(f"Parsed PRD: {len(prd.user_stories)} stories")
        return prd

    def generate_prd(self, project_name: str | None = None) -> PRDDocument:
        """Generate PRD from discovery findings.

        Uses the PM agent to generate structured PRD content from the
        collected discovery findings.

        Args:
            project_name: Optional override for project name.

        Returns:
            Generated PRDDocument.

        Raises:
            ValueError: If discovery is not complete.
        """
        if not self.pm_agent.findings.is_complete():
            raise ValueError(
                "Discovery is not complete. Run the discovery interview first."
            )

        log_agent_action("PRDGenerator", "Generating PRD from discovery findings")

        findings = self.pm_agent.get_findings()

        # Generate PRD using LLM
        prompt = PRD_GENERATION_PROMPT.format(
            problem=findings["problem"],
            users=findings["users"],
            features=findings["features"],
            success=findings["success"],
            scope=findings["scope"],
        )

        response = self.pm_agent.chat(prompt)
        self.prd = self._parse_prd_response(response)

        # Allow project name override
        if project_name:
            self.prd.project_name = project_name

        log_agent_action(
            "PRDGenerator",
            "PRD generated",
            f"{len(self.prd.user_stories)} user stories",
        )

        return self.prd

    def save_prd(self, path: str | None = None) -> Path:
        """Save PRD to markdown file.

        Args:
            path: Optional override for output path.

        Returns:
            Path where PRD was saved.
        """
        output_path = path or self.output_path

        if not self.prd.project_name:
            raise ValueError("No PRD generated. Call generate_prd() first.")

        markdown = self.prd.to_markdown()
        saved_path = write_file(output_path, markdown)

        log_agent_action("PRDGenerator", "PRD saved", str(saved_path))

        return saved_path

    def run_full_workflow(
        self,
        responses: dict[str, str],
        project_name: str | None = None,
    ) -> PRDDocument:
        """Run the complete PRD generation workflow.

        This is a convenience method that runs the entire workflow
        with pre-provided responses (useful for testing or automation).

        Args:
            responses: Dict mapping discovery phases to responses:
                - problem: Problem description
                - users: Target users
                - features: Core features (top 3)
                - success: Success criteria
                - scope: Out of scope items
            project_name: Optional project name override.

        Returns:
            Generated PRDDocument.
        """
        log_agent_action("PRDGenerator", "Running full PRD workflow")

        # Manually populate findings
        self.pm_agent.findings.problem = responses.get("problem", "")
        self.pm_agent.findings.users = responses.get("users", "")
        self.pm_agent.findings.features = responses.get("features", "")
        self.pm_agent.findings.success = responses.get("success", "")
        self.pm_agent.findings.scope = responses.get("scope", "")

        # Mark interview as complete
        self.pm_agent.current_phase = DiscoveryPhase.COMPLETE

        # Generate and save PRD
        self.generate_prd(project_name)
        self.save_prd()

        return self.prd

    def reset(self) -> None:
        """Reset the workflow for a new project."""
        self.pm_agent.reset_interview()
        self.prd = PRDDocument()
        log_agent_action("PRDGenerator", "Workflow reset")
