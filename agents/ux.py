"""UX Designer Agent for MAT.

The UXDesignerAgent designs user interfaces and user experiences.
It creates component specifications, defines user flows and interactions,
and follows accessibility best practices.
"""

from dataclasses import dataclass, field

from agents.base import BaseAgent
from llm.client import OllamaClient


UX_DESIGNER_SYSTEM_PROMPT = """You are a UX Designer agent creating user interface designs.

Your role is to:
1. Create component specifications for UI elements
2. Define user flows and interactions
3. Ensure accessibility best practices (WCAG 2.1 AA compliance)
4. Design intuitive, user-friendly interfaces

Guidelines:
- Prioritize usability and clarity over aesthetics
- Consider users with different abilities (visual, motor, cognitive)
- Design for the smallest common denominator (mobile-first when applicable)
- Keep interfaces simple - avoid cognitive overload
- Provide clear feedback for user actions
- Use consistent patterns throughout the application

Accessibility considerations:
- Ensure sufficient color contrast (4.5:1 for normal text, 3:1 for large text)
- Provide text alternatives for non-text content
- Ensure keyboard navigability
- Use semantic HTML elements
- Support screen readers with ARIA labels where needed
- Avoid relying solely on color to convey information

Output structured specifications that developers can implement."""


@dataclass
class ComponentSpec:
    """Specification for a UI component."""

    name: str
    description: str
    props: list[str] = field(default_factory=list)
    accessibility: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, str | list[str]]:
        """Convert spec to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "props": self.props,
            "accessibility": self.accessibility,
            "states": self.states,
        }

    def to_markdown(self) -> str:
        """Convert spec to markdown format."""
        props_str = "\n".join(f"  - {p}" for p in self.props) if self.props else "  - None"
        a11y_str = "\n".join(f"  - {a}" for a in self.accessibility) if self.accessibility else "  - None"
        states_str = "\n".join(f"  - {s}" for s in self.states) if self.states else "  - None"
        return (
            f"### {self.name}\n\n"
            f"{self.description}\n\n"
            f"**Props**:\n{props_str}\n\n"
            f"**Accessibility**:\n{a11y_str}\n\n"
            f"**States**:\n{states_str}\n"
        )


@dataclass
class UserFlowStep:
    """A step in a user flow."""

    step_number: int
    action: str
    expected_result: str
    notes: str = ""

    def to_dict(self) -> dict[str, int | str]:
        """Convert step to a dictionary."""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "expected_result": self.expected_result,
            "notes": self.notes,
        }


@dataclass
class UserFlow:
    """A complete user flow through the application."""

    name: str
    description: str
    steps: list[UserFlowStep] = field(default_factory=list)
    entry_point: str = ""
    exit_point: str = ""

    def to_dict(self) -> dict[str, str | list[dict[str, int | str]]]:
        """Convert flow to a dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "entry_point": self.entry_point,
            "exit_point": self.exit_point,
        }

    def to_markdown(self) -> str:
        """Convert flow to markdown format."""
        steps_md = ""
        for step in self.steps:
            notes = f" ({step.notes})" if step.notes else ""
            steps_md += f"{step.step_number}. **{step.action}**{notes}\n   → {step.expected_result}\n"

        return (
            f"### {self.name}\n\n"
            f"{self.description}\n\n"
            f"**Entry Point**: {self.entry_point}\n"
            f"**Exit Point**: {self.exit_point}\n\n"
            f"**Steps**:\n{steps_md}"
        )


@dataclass
class InteractionSpec:
    """Specification for a user interaction."""

    trigger: str
    action: str
    feedback: str
    accessibility_note: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert spec to a dictionary."""
        return {
            "trigger": self.trigger,
            "action": self.action,
            "feedback": self.feedback,
            "accessibility_note": self.accessibility_note,
        }


@dataclass
class UXDocument:
    """Complete UX documentation for a project."""

    overview: str = ""
    components: list[ComponentSpec] = field(default_factory=list)
    user_flows: list[UserFlow] = field(default_factory=list)
    interactions: list[InteractionSpec] = field(default_factory=list)
    accessibility_notes: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert UX document to markdown format."""
        sections = [
            f"# UX Design Document\n\n## Overview\n\n{self.overview}\n",
        ]

        # Components section
        if self.components:
            sections.append("## Components\n")
            for comp in self.components:
                sections.append(comp.to_markdown())

        # User flows section
        if self.user_flows:
            sections.append("\n## User Flows\n")
            for flow in self.user_flows:
                sections.append(flow.to_markdown())

        # Interactions section
        if self.interactions:
            sections.append("\n## Interactions\n")
            for interaction in self.interactions:
                a11y = f"\n   - A11y: {interaction.accessibility_note}" if interaction.accessibility_note else ""
                sections.append(
                    f"- **{interaction.trigger}**: {interaction.action}\n"
                    f"   - Feedback: {interaction.feedback}{a11y}\n"
                )

        # Accessibility notes section
        if self.accessibility_notes:
            sections.append("\n## Accessibility Notes\n")
            for note in self.accessibility_notes:
                sections.append(f"- {note}\n")

        return "\n".join(sections)


@dataclass
class UXDesignerAgent(BaseAgent):
    """UX Designer agent that creates user interface designs.

    Attributes:
        ux_document: The current UX document being developed.
    """

    name: str = field(default="UX Designer")
    role: str = field(default="Design user interfaces and user experiences")
    system_prompt: str = field(default=UX_DESIGNER_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    ux_document: UXDocument = field(default_factory=UXDocument)

    def create_component_spec(self, component_name: str, requirements: str) -> ComponentSpec:
        """Create a specification for a UI component.

        Args:
            component_name: Name of the component to design.
            requirements: Requirements or context for the component.

        Returns:
            A ComponentSpec with the design details.
        """
        prompt = (
            f"Create a UI component specification for '{component_name}':\n\n"
            f"Requirements:\n{requirements}\n\n"
            "Respond in this exact format:\n"
            "NAME: [component name]\n"
            "DESCRIPTION: [what the component does]\n"
            "PROPS: [comma-separated list of props/inputs]\n"
            "ACCESSIBILITY: [comma-separated list of accessibility features]\n"
            "STATES: [comma-separated list of visual states like default, hover, disabled, error]"
        )

        response = self.chat(prompt)
        spec = self._parse_component_response(response)
        self.ux_document.components.append(spec)
        return spec

    def _parse_component_response(self, response: str) -> ComponentSpec:
        """Parse LLM response into a ComponentSpec.

        Args:
            response: The raw LLM response.

        Returns:
            Parsed ComponentSpec.
        """
        name = ""
        description = ""
        props: list[str] = []
        accessibility: list[str] = []
        states: list[str] = []

        for line in response.strip().split("\n"):
            line_upper = line.upper()
            if line_upper.startswith("NAME:"):
                name = line.split(":", 1)[1].strip()
            elif line_upper.startswith("DESCRIPTION:"):
                description = line.split(":", 1)[1].strip()
            elif line_upper.startswith("PROPS:"):
                props_str = line.split(":", 1)[1].strip()
                if props_str.lower() != "none":
                    props = [p.strip() for p in props_str.split(",")]
            elif line_upper.startswith("ACCESSIBILITY:"):
                a11y_str = line.split(":", 1)[1].strip()
                if a11y_str.lower() != "none":
                    accessibility = [a.strip() for a in a11y_str.split(",")]
            elif line_upper.startswith("STATES:"):
                states_str = line.split(":", 1)[1].strip()
                if states_str.lower() != "none":
                    states = [s.strip() for s in states_str.split(",")]

        return ComponentSpec(
            name=name or "Unknown",
            description=description,
            props=props,
            accessibility=accessibility,
            states=states,
        )

    def define_user_flow(self, flow_name: str, requirements: str) -> UserFlow:
        """Define a user flow through the application.

        Args:
            flow_name: Name of the user flow (e.g., "User Registration").
            requirements: Requirements or context for the flow.

        Returns:
            A UserFlow with the defined steps.
        """
        prompt = (
            f"Define the user flow for '{flow_name}':\n\n"
            f"Requirements:\n{requirements}\n\n"
            "Respond in this exact format:\n"
            "NAME: [flow name]\n"
            "DESCRIPTION: [what this flow accomplishes]\n"
            "ENTRY_POINT: [where the user starts]\n"
            "EXIT_POINT: [where the user ends up]\n"
            "STEPS:\n"
            "1. ACTION: [what user does] | RESULT: [what happens]\n"
            "2. ACTION: [what user does] | RESULT: [what happens]\n"
            "(continue numbering as needed)"
        )

        response = self.chat(prompt)
        flow = self._parse_user_flow_response(response)
        self.ux_document.user_flows.append(flow)
        return flow

    def _parse_user_flow_response(self, response: str) -> UserFlow:
        """Parse LLM response into a UserFlow.

        Args:
            response: The raw LLM response.

        Returns:
            Parsed UserFlow.
        """
        name = ""
        description = ""
        entry_point = ""
        exit_point = ""
        steps: list[UserFlowStep] = []

        lines = response.strip().split("\n")
        in_steps = False

        for line in lines:
            line_stripped = line.strip()
            line_upper = line_stripped.upper()

            if line_upper.startswith("NAME:"):
                name = line_stripped.split(":", 1)[1].strip()
            elif line_upper.startswith("DESCRIPTION:"):
                description = line_stripped.split(":", 1)[1].strip()
            elif line_upper.startswith("ENTRY_POINT:"):
                entry_point = line_stripped.split(":", 1)[1].strip()
            elif line_upper.startswith("EXIT_POINT:"):
                exit_point = line_stripped.split(":", 1)[1].strip()
            elif line_upper.startswith("STEPS:"):
                in_steps = True
            elif in_steps and line_stripped and line_stripped[0].isdigit():
                # Parse step line: "1. ACTION: ... | RESULT: ..."
                step = self._parse_step_line(line_stripped)
                if step:
                    steps.append(step)

        return UserFlow(
            name=name or "Unknown Flow",
            description=description,
            steps=steps,
            entry_point=entry_point,
            exit_point=exit_point,
        )

    def _parse_step_line(self, line: str) -> UserFlowStep | None:
        """Parse a single step line from user flow response.

        Args:
            line: A line like "1. ACTION: click button | RESULT: modal opens"

        Returns:
            Parsed UserFlowStep or None if parsing fails.
        """
        # Remove step number prefix
        parts = line.split(".", 1)
        if len(parts) != 2:
            return None

        step_num = int(parts[0].strip()) if parts[0].strip().isdigit() else 0
        content = parts[1].strip()

        # Split by | to get ACTION and RESULT
        if "|" in content:
            action_part, result_part = content.split("|", 1)
        else:
            action_part = content
            result_part = ""

        # Extract action
        action = action_part.replace("ACTION:", "").strip()
        if action.upper().startswith("ACTION:"):
            action = action[7:].strip()

        # Extract result
        result = result_part.replace("RESULT:", "").strip()
        if result.upper().startswith("RESULT:"):
            result = result[7:].strip()

        if not action:
            return None

        return UserFlowStep(
            step_number=step_num,
            action=action,
            expected_result=result,
        )

    def define_interactions(self, context: str) -> list[InteractionSpec]:
        """Define interactions for the application.

        Args:
            context: Context about the application and its components.

        Returns:
            List of InteractionSpec objects.
        """
        prompt = (
            f"Define key user interactions for this application:\n\n"
            f"{context}\n\n"
            "For each interaction, provide:\n"
            "TRIGGER: [what causes the interaction - click, hover, keypress, etc.]\n"
            "ACTION: [what the interaction does]\n"
            "FEEDBACK: [visual/audio feedback to user]\n"
            "A11Y: [accessibility consideration for this interaction]\n"
            "---\n"
            "List 5-10 important interactions, separated by '---'."
        )

        response = self.chat(prompt)
        interactions = self._parse_interactions_response(response)
        self.ux_document.interactions = interactions
        return interactions

    def _parse_interactions_response(self, response: str) -> list[InteractionSpec]:
        """Parse LLM response into a list of InteractionSpec.

        Args:
            response: The raw LLM response.

        Returns:
            List of parsed InteractionSpec objects.
        """
        interactions: list[InteractionSpec] = []
        blocks = response.strip().split("---")

        for block in blocks:
            if not block.strip():
                continue

            trigger = ""
            action = ""
            feedback = ""
            a11y_note = ""

            for line in block.strip().split("\n"):
                line_upper = line.upper()
                if line_upper.startswith("TRIGGER:"):
                    trigger = line.split(":", 1)[1].strip()
                elif line_upper.startswith("ACTION:"):
                    action = line.split(":", 1)[1].strip()
                elif line_upper.startswith("FEEDBACK:"):
                    feedback = line.split(":", 1)[1].strip()
                elif line_upper.startswith("A11Y:"):
                    a11y_note = line.split(":", 1)[1].strip()

            if trigger and action:
                interactions.append(InteractionSpec(
                    trigger=trigger,
                    action=action,
                    feedback=feedback,
                    accessibility_note=a11y_note,
                ))

        return interactions

    def add_accessibility_note(self, note: str) -> None:
        """Add an accessibility note to the UX document.

        Args:
            note: The accessibility note to add.
        """
        self.ux_document.accessibility_notes.append(note)

    def analyze_accessibility(self, requirements: str) -> list[str]:
        """Analyze requirements for accessibility considerations.

        Args:
            requirements: Project requirements to analyze.

        Returns:
            List of accessibility recommendations.
        """
        prompt = (
            f"Analyze these requirements for accessibility (WCAG 2.1 AA):\n\n"
            f"{requirements}\n\n"
            "Provide specific accessibility recommendations:\n"
            "- One recommendation per line\n"
            "- Focus on practical, implementable guidance\n"
            "- Consider visual, motor, and cognitive accessibility\n"
            "- Include color contrast, keyboard navigation, screen readers"
        )

        response = self.chat(prompt)
        notes = [
            line.strip().lstrip("- •")
            for line in response.strip().split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        self.ux_document.accessibility_notes = notes
        return notes

    def create_full_ux_design(self, requirements: str, overview: str = "") -> UXDocument:
        """Create a complete UX design document.

        This method orchestrates the full UX design process:
        1. Sets overview
        2. Analyzes accessibility requirements
        3. Defines main user flow
        4. Creates key component specs

        Args:
            requirements: Full project requirements.
            overview: Optional overview text to include.

        Returns:
            Complete UXDocument.
        """
        # Set overview
        if overview:
            self.ux_document.overview = overview
        else:
            overview_prompt = (
                f"Write a 2-3 sentence UX design overview for this project:\n\n"
                f"{requirements}"
            )
            self.ux_document.overview = self.chat(overview_prompt)

        # Analyze accessibility
        self.analyze_accessibility(requirements)

        # Define main user flow
        self.define_user_flow("Main User Flow", requirements)

        # Define interactions
        self.define_interactions(requirements)

        return self.ux_document

    def get_ux_markdown(self) -> str:
        """Get the current UX design as markdown.

        Returns:
            Markdown formatted UX document.
        """
        return self.ux_document.to_markdown()

    def reset_ux_document(self) -> None:
        """Reset the UX document to start fresh."""
        self.ux_document = UXDocument()
        self.clear_history()
