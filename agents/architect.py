"""Architect Agent for MAT.

The ArchitectAgent designs technical solutions for projects.
It proposes tech stacks, identifies components, APIs, and data models,
and documents architecture decisions.
"""

from dataclasses import dataclass, field

from agents.base import BaseAgent
from llm.client import OllamaClient


ARCHITECT_SYSTEM_PROMPT = """You are a Software Architect agent designing technical solutions.

Your role is to:
1. Analyze project requirements and propose appropriate tech stacks
2. Identify system components and their responsibilities
3. Design APIs and data models
4. Document architecture decisions with clear rationale

Guidelines:
- Match technology choices to project scale and requirements
- Consider maintainability, scalability, and developer experience
- Keep solutions simple - avoid over-engineering
- Provide clear justification for each technical decision
- Identify potential risks and trade-offs

When proposing a tech stack, consider:
- Project type (web, API, CLI, mobile, etc.)
- Team size and expertise
- Performance requirements
- Deployment environment
- Integration needs

Output structured documentation that can be used by development teams."""


@dataclass
class TechStackProposal:
    """A proposed technology stack for a project."""

    language: str = ""
    framework: str = ""
    database: str = ""
    additional_tools: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, str | list[str]]:
        """Convert proposal to a dictionary."""
        return {
            "language": self.language,
            "framework": self.framework,
            "database": self.database,
            "additional_tools": self.additional_tools,
            "rationale": self.rationale,
        }

    def to_markdown(self) -> str:
        """Convert proposal to markdown format."""
        tools_str = ", ".join(self.additional_tools) if self.additional_tools else "None"
        return (
            f"## Tech Stack\n\n"
            f"- **Language**: {self.language}\n"
            f"- **Framework**: {self.framework}\n"
            f"- **Database**: {self.database}\n"
            f"- **Additional Tools**: {tools_str}\n\n"
            f"### Rationale\n\n{self.rationale}\n"
        )


@dataclass
class ComponentSpec:
    """Specification for a system component."""

    name: str
    responsibility: str
    interfaces: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, str | list[str]]:
        """Convert spec to a dictionary."""
        return {
            "name": self.name,
            "responsibility": self.responsibility,
            "interfaces": self.interfaces,
        }


@dataclass
class DataModel:
    """Specification for a data model/entity."""

    name: str
    fields: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, str | list[str]]:
        """Convert model to a dictionary."""
        return {
            "name": self.name,
            "fields": self.fields,
            "relationships": self.relationships,
        }


@dataclass
class ArchitectureDocument:
    """Complete architecture documentation for a project."""

    overview: str = ""
    tech_stack: TechStackProposal = field(default_factory=TechStackProposal)
    components: list[ComponentSpec] = field(default_factory=list)
    data_models: list[DataModel] = field(default_factory=list)
    api_endpoints: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert architecture document to markdown format."""
        sections = [
            f"# Architecture Document\n\n## Overview\n\n{self.overview}\n",
            self.tech_stack.to_markdown(),
        ]

        # Components section
        if self.components:
            sections.append("## Components\n")
            for comp in self.components:
                interfaces_str = ", ".join(comp.interfaces) if comp.interfaces else "None"
                sections.append(
                    f"### {comp.name}\n\n"
                    f"**Responsibility**: {comp.responsibility}\n\n"
                    f"**Interfaces**: {interfaces_str}\n"
                )

        # Data models section
        if self.data_models:
            sections.append("## Data Models\n")
            for model in self.data_models:
                fields_str = "\n".join(f"  - {f}" for f in model.fields) if model.fields else "  - None"
                rels_str = "\n".join(f"  - {r}" for r in model.relationships) if model.relationships else "  - None"
                sections.append(
                    f"### {model.name}\n\n"
                    f"**Fields**:\n{fields_str}\n\n"
                    f"**Relationships**:\n{rels_str}\n"
                )

        # API endpoints section
        if self.api_endpoints:
            sections.append("## API Endpoints\n")
            for endpoint in self.api_endpoints:
                sections.append(f"- {endpoint}\n")

        # Architecture decisions section
        if self.decisions:
            sections.append("\n## Architecture Decisions\n")
            for i, decision in enumerate(self.decisions, 1):
                sections.append(f"{i}. {decision}\n")

        return "\n".join(sections)


@dataclass
class ArchitectAgent(BaseAgent):
    """Architect agent that designs technical solutions.

    Attributes:
        architecture: The current architecture document being developed.
    """

    name: str = field(default="Architect")
    role: str = field(default="Design technical solutions and system architecture")
    system_prompt: str = field(default=ARCHITECT_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    architecture: ArchitectureDocument = field(default_factory=ArchitectureDocument)

    def propose_tech_stack(self, requirements: str) -> TechStackProposal:
        """Propose a technology stack based on project requirements.

        Args:
            requirements: Description of project requirements.

        Returns:
            A TechStackProposal with recommended technologies.
        """
        prompt = (
            f"Based on these requirements, propose a technology stack:\n\n"
            f"{requirements}\n\n"
            "Respond in this exact format (keep each line short):\n"
            "LANGUAGE: [programming language]\n"
            "FRAMEWORK: [main framework or 'None']\n"
            "DATABASE: [database or 'None']\n"
            "TOOLS: [comma-separated list of additional tools or 'None']\n"
            "RATIONALE: [2-3 sentences explaining choices]"
        )

        response = self.chat(prompt)
        return self._parse_tech_stack_response(response)

    def _parse_tech_stack_response(self, response: str) -> TechStackProposal:
        """Parse LLM response into a TechStackProposal.

        Args:
            response: The raw LLM response.

        Returns:
            Parsed TechStackProposal.
        """
        proposal = TechStackProposal()
        lines = response.strip().split("\n")

        for line in lines:
            line_upper = line.upper()
            if line_upper.startswith("LANGUAGE:"):
                proposal.language = line.split(":", 1)[1].strip()
            elif line_upper.startswith("FRAMEWORK:"):
                proposal.framework = line.split(":", 1)[1].strip()
            elif line_upper.startswith("DATABASE:"):
                proposal.database = line.split(":", 1)[1].strip()
            elif line_upper.startswith("TOOLS:"):
                tools_str = line.split(":", 1)[1].strip()
                if tools_str.lower() != "none":
                    proposal.additional_tools = [t.strip() for t in tools_str.split(",")]
            elif line_upper.startswith("RATIONALE:"):
                proposal.rationale = line.split(":", 1)[1].strip()

        self.architecture.tech_stack = proposal
        return proposal

    def identify_components(self, requirements: str) -> list[ComponentSpec]:
        """Identify system components based on requirements.

        Args:
            requirements: Description of project requirements.

        Returns:
            List of ComponentSpec objects.
        """
        prompt = (
            f"Based on these requirements, identify the main system components:\n\n"
            f"{requirements}\n\n"
            "For each component, provide:\n"
            "COMPONENT: [name]\n"
            "RESPONSIBILITY: [what it does]\n"
            "INTERFACES: [comma-separated list of interfaces/APIs it exposes]\n"
            "---\n"
            "List 3-5 components, separated by '---'."
        )

        response = self.chat(prompt)
        components = self._parse_components_response(response)
        self.architecture.components = components
        return components

    def _parse_components_response(self, response: str) -> list[ComponentSpec]:
        """Parse LLM response into a list of ComponentSpec.

        Args:
            response: The raw LLM response.

        Returns:
            List of parsed ComponentSpec objects.
        """
        components: list[ComponentSpec] = []
        blocks = response.strip().split("---")

        for block in blocks:
            if not block.strip():
                continue

            name = ""
            responsibility = ""
            interfaces: list[str] = []

            for line in block.strip().split("\n"):
                line_upper = line.upper()
                if line_upper.startswith("COMPONENT:"):
                    name = line.split(":", 1)[1].strip()
                elif line_upper.startswith("RESPONSIBILITY:"):
                    responsibility = line.split(":", 1)[1].strip()
                elif line_upper.startswith("INTERFACES:"):
                    interfaces_str = line.split(":", 1)[1].strip()
                    if interfaces_str.lower() != "none":
                        interfaces = [i.strip() for i in interfaces_str.split(",")]

            if name and responsibility:
                components.append(ComponentSpec(
                    name=name,
                    responsibility=responsibility,
                    interfaces=interfaces,
                ))

        return components

    def design_data_models(self, requirements: str) -> list[DataModel]:
        """Design data models/entities for the project.

        Args:
            requirements: Description of project requirements.

        Returns:
            List of DataModel objects.
        """
        prompt = (
            f"Based on these requirements, design the data models/entities:\n\n"
            f"{requirements}\n\n"
            "For each data model, provide:\n"
            "MODEL: [name]\n"
            "FIELDS: [comma-separated list of field names]\n"
            "RELATIONSHIPS: [comma-separated list like 'has_many: X' or 'belongs_to: Y']\n"
            "---\n"
            "List all necessary models, separated by '---'."
        )

        response = self.chat(prompt)
        models = self._parse_data_models_response(response)
        self.architecture.data_models = models
        return models

    def _parse_data_models_response(self, response: str) -> list[DataModel]:
        """Parse LLM response into a list of DataModel.

        Args:
            response: The raw LLM response.

        Returns:
            List of parsed DataModel objects.
        """
        models: list[DataModel] = []
        blocks = response.strip().split("---")

        for block in blocks:
            if not block.strip():
                continue

            name = ""
            fields: list[str] = []
            relationships: list[str] = []

            for line in block.strip().split("\n"):
                line_upper = line.upper()
                if line_upper.startswith("MODEL:"):
                    name = line.split(":", 1)[1].strip()
                elif line_upper.startswith("FIELDS:"):
                    fields_str = line.split(":", 1)[1].strip()
                    if fields_str.lower() != "none":
                        fields = [f.strip() for f in fields_str.split(",")]
                elif line_upper.startswith("RELATIONSHIPS:"):
                    rels_str = line.split(":", 1)[1].strip()
                    if rels_str.lower() != "none":
                        relationships = [r.strip() for r in rels_str.split(",")]

            if name:
                models.append(DataModel(
                    name=name,
                    fields=fields,
                    relationships=relationships,
                ))

        return models

    def design_api(self, requirements: str) -> list[str]:
        """Design API endpoints for the project.

        Args:
            requirements: Description of project requirements.

        Returns:
            List of API endpoint descriptions.
        """
        prompt = (
            f"Based on these requirements, design the API endpoints:\n\n"
            f"{requirements}\n\n"
            "List API endpoints in this format:\n"
            "METHOD /path - description\n\n"
            "Example:\n"
            "GET /users - List all users\n"
            "POST /users - Create a new user\n"
            "GET /users/:id - Get user by ID"
        )

        response = self.chat(prompt)
        endpoints = [
            line.strip()
            for line in response.strip().split("\n")
            if line.strip() and ("/" in line or line.upper().startswith(("GET", "POST", "PUT", "DELETE", "PATCH")))
        ]
        self.architecture.api_endpoints = endpoints
        return endpoints

    def document_decision(self, decision: str, rationale: str) -> None:
        """Document an architecture decision.

        Args:
            decision: The decision that was made.
            rationale: The reasoning behind the decision.
        """
        formatted = f"{decision} - {rationale}"
        self.architecture.decisions.append(formatted)

    def create_full_architecture(self, requirements: str, overview: str = "") -> ArchitectureDocument:
        """Create a complete architecture document.

        This method orchestrates the full architecture design process:
        1. Proposes tech stack
        2. Identifies components
        3. Designs data models
        4. Designs API endpoints

        Args:
            requirements: Full project requirements.
            overview: Optional overview text to include.

        Returns:
            Complete ArchitectureDocument.
        """
        # Set overview
        if overview:
            self.architecture.overview = overview
        else:
            # Generate overview from requirements
            overview_prompt = (
                f"Write a 2-3 sentence architecture overview for this project:\n\n"
                f"{requirements}"
            )
            self.architecture.overview = self.chat(overview_prompt)

        # Generate all architecture components
        self.propose_tech_stack(requirements)
        self.identify_components(requirements)
        self.design_data_models(requirements)
        self.design_api(requirements)

        return self.architecture

    def get_architecture_markdown(self) -> str:
        """Get the current architecture as markdown.

        Returns:
            Markdown formatted architecture document.
        """
        return self.architecture.to_markdown()

    def reset_architecture(self) -> None:
        """Reset the architecture document to start fresh."""
        self.architecture = ArchitectureDocument()
        self.clear_history()
