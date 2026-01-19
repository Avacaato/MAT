"""Scale-adaptive intelligence for MAT.

Adjusts planning depth based on project complexity. Small tasks don't need
enterprise-level planning; bug fixes can go directly to the developer.

Complexity Levels:
- Level 0: Bug fix - minimal planning, direct to Developer
- Level 1: Small feature - PM + Developer
- Level 2: Product - Full workflow (PM, Architect, Developer, QA)
- Level 3: Enterprise - Extended workflows with compliance checks
- Level 4: Enterprise+ - Full audit trail and multi-team coordination
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from agents.base import BaseAgent
from llm.client import OllamaClient
from orchestrator.coordinator import AgentType
from utils.logger import log_agent_action, log_agent_decision


class ComplexityLevel(IntEnum):
    """Project complexity levels."""

    BUG_FIX = 0  # Minimal planning, direct to developer
    SMALL_FEATURE = 1  # PM + Developer
    PRODUCT = 2  # Full workflow: PM, Architect, Developer, QA
    ENTERPRISE = 3  # Extended workflow with compliance
    ENTERPRISE_PLUS = 4  # Full audit trail, multi-team


@dataclass
class ScaleAssessment:
    """Result of complexity assessment.

    Attributes:
        level: Detected complexity level.
        confidence: Confidence score (0.0-1.0).
        reasoning: Explanation for the assessment.
        indicators: List of indicators that influenced the assessment.
        recommended_agents: Agent types to involve based on level.
        recommended_workflow: Workflow steps for this complexity.
    """

    level: ComplexityLevel
    confidence: float
    reasoning: str
    indicators: list[str] = field(default_factory=list)
    recommended_agents: list[AgentType] = field(default_factory=list)
    recommended_workflow: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert assessment to dictionary format."""
        return {
            "level": self.level.value,
            "level_name": self.level.name,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "indicators": self.indicators,
            "recommended_agents": [a.value for a in self.recommended_agents],
            "recommended_workflow": self.recommended_workflow,
        }

    def to_markdown(self) -> str:
        """Convert assessment to markdown format."""
        lines = [
            "## Scale Assessment",
            f"**Level**: {self.level.value} - {self.level.name}",
            f"**Confidence**: {self.confidence:.0%}",
            "",
            "### Reasoning",
            self.reasoning,
            "",
            "### Indicators",
        ]
        for indicator in self.indicators:
            lines.append(f"- {indicator}")

        lines.extend(
            [
                "",
                "### Recommended Agents",
            ]
        )
        for agent in self.recommended_agents:
            lines.append(f"- {agent.value}")

        lines.extend(
            [
                "",
                "### Recommended Workflow",
            ]
        )
        for i, step in enumerate(self.recommended_workflow, 1):
            lines.append(f"{i}. {step}")

        return "\n".join(lines)


# Level-based workflow definitions
LEVEL_WORKFLOWS: dict[ComplexityLevel, list[tuple[AgentType, str]]] = {
    ComplexityLevel.BUG_FIX: [
        (AgentType.DEVELOPER, "Analyze and fix the bug"),
        (AgentType.QA_TESTER, "Verify the fix"),
    ],
    ComplexityLevel.SMALL_FEATURE: [
        (AgentType.PRODUCT_MANAGER, "Clarify requirements"),
        (AgentType.DEVELOPER, "Implement the feature"),
        (AgentType.QA_TESTER, "Verify implementation"),
    ],
    ComplexityLevel.PRODUCT: [
        (AgentType.PRODUCT_MANAGER, "Discovery and requirements"),
        (AgentType.ARCHITECT, "Technical design"),
        (AgentType.UX_DESIGNER, "UX design"),
        (AgentType.DEVELOPER, "Implementation"),
        (AgentType.QA_TESTER, "Testing and verification"),
    ],
    ComplexityLevel.ENTERPRISE: [
        (AgentType.PRODUCT_MANAGER, "Discovery and requirements"),
        (AgentType.ARCHITECT, "Technical design with compliance"),
        (AgentType.UX_DESIGNER, "UX design with accessibility"),
        (AgentType.SCRUM_MASTER, "Sprint planning"),
        (AgentType.DEVELOPER, "Implementation"),
        (AgentType.QA_TESTER, "Testing with compliance verification"),
    ],
    ComplexityLevel.ENTERPRISE_PLUS: [
        (AgentType.PRODUCT_MANAGER, "Discovery with stakeholder analysis"),
        (AgentType.ARCHITECT, "Architecture review board preparation"),
        (AgentType.UX_DESIGNER, "Full UX research and design"),
        (AgentType.SCRUM_MASTER, "Multi-sprint planning"),
        (AgentType.DEVELOPER, "Phased implementation"),
        (AgentType.QA_TESTER, "Full test suite with audit trail"),
        (AgentType.SCRUM_MASTER, "Release coordination"),
    ],
}

# Agent recommendations by level
LEVEL_AGENTS: dict[ComplexityLevel, list[AgentType]] = {
    ComplexityLevel.BUG_FIX: [AgentType.DEVELOPER, AgentType.QA_TESTER],
    ComplexityLevel.SMALL_FEATURE: [
        AgentType.PRODUCT_MANAGER,
        AgentType.DEVELOPER,
        AgentType.QA_TESTER,
    ],
    ComplexityLevel.PRODUCT: [
        AgentType.PRODUCT_MANAGER,
        AgentType.ARCHITECT,
        AgentType.UX_DESIGNER,
        AgentType.DEVELOPER,
        AgentType.QA_TESTER,
    ],
    ComplexityLevel.ENTERPRISE: [
        AgentType.PRODUCT_MANAGER,
        AgentType.ARCHITECT,
        AgentType.UX_DESIGNER,
        AgentType.SCRUM_MASTER,
        AgentType.DEVELOPER,
        AgentType.QA_TESTER,
    ],
    ComplexityLevel.ENTERPRISE_PLUS: [
        AgentType.PRODUCT_MANAGER,
        AgentType.ARCHITECT,
        AgentType.UX_DESIGNER,
        AgentType.SCRUM_MASTER,
        AgentType.DEVELOPER,
        AgentType.QA_TESTER,
    ],
}

# Keywords that indicate complexity levels
LEVEL_KEYWORDS: dict[ComplexityLevel, list[str]] = {
    ComplexityLevel.BUG_FIX: [
        "bug",
        "fix",
        "error",
        "crash",
        "typo",
        "broken",
        "doesn't work",
        "not working",
        "issue",
        "patch",
    ],
    ComplexityLevel.SMALL_FEATURE: [
        "add",
        "simple",
        "small",
        "button",
        "field",
        "quick",
        "minor",
        "tweak",
        "update",
        "change",
    ],
    ComplexityLevel.PRODUCT: [
        "feature",
        "new functionality",
        "user story",
        "requirement",
        "design",
        "implement",
        "build",
        "create",
    ],
    ComplexityLevel.ENTERPRISE: [
        "compliance",
        "security",
        "audit",
        "regulation",
        "enterprise",
        "scale",
        "performance",
        "sla",
    ],
    ComplexityLevel.ENTERPRISE_PLUS: [
        "multi-team",
        "cross-functional",
        "organization-wide",
        "platform",
        "infrastructure",
        "migration",
        "transformation",
    ],
}


SCALE_ADAPTER_SYSTEM_PROMPT = """You are a Scale Adapter that analyzes project complexity.

Your job is to determine the appropriate level of planning for a project based on its description.

Complexity Levels:
- Level 0 (BUG_FIX): Simple fixes, typos, minor corrections
- Level 1 (SMALL_FEATURE): Adding a button, field, or simple component
- Level 2 (PRODUCT): New features requiring design and testing
- Level 3 (ENTERPRISE): Features with compliance, security, or scale requirements
- Level 4 (ENTERPRISE_PLUS): Platform-level changes, multi-team coordination

Guidelines:
- Default to the simplest level that fits the task
- Don't over-engineer small tasks
- Look for keywords indicating complexity
- Consider scope, dependencies, and risk

When analyzing, output:
LEVEL: [0-4]
CONFIDENCE: [0.0-1.0]
REASONING: [brief explanation]
INDICATORS: [comma-separated list of complexity indicators found]"""


@dataclass
class ScaleAdapter(BaseAgent):
    """Analyzes project complexity and recommends appropriate planning depth.

    The ScaleAdapter examines project descriptions and requirements to determine
    the appropriate level of planning and which agents should be involved.

    Attributes:
        name: Agent name.
        role: Agent role description.
        system_prompt: System prompt for LLM.
        client: LLM client instance.
        last_assessment: Most recent scale assessment.
    """

    name: str = field(default="ScaleAdapter")
    role: str = field(default="Analyze project complexity and adapt planning depth")
    system_prompt: str = field(default=SCALE_ADAPTER_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    last_assessment: ScaleAssessment | None = field(default=None)

    def _detect_keywords(self, text: str) -> dict[ComplexityLevel, list[str]]:
        """Detect complexity-indicating keywords in text.

        Args:
            text: Text to analyze.

        Returns:
            Dictionary mapping levels to found keywords.
        """
        text_lower = text.lower()
        found: dict[ComplexityLevel, list[str]] = {}

        for level, keywords in LEVEL_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in text_lower]
            if matches:
                found[level] = matches

        return found

    def _keyword_based_assessment(self, description: str) -> tuple[ComplexityLevel, float, list[str]]:
        """Perform keyword-based complexity assessment.

        Args:
            description: Project description to analyze.

        Returns:
            Tuple of (level, confidence, indicators).
        """
        found_keywords = self._detect_keywords(description)

        if not found_keywords:
            # Default to PRODUCT level if no keywords found
            return ComplexityLevel.PRODUCT, 0.5, ["No specific complexity indicators found"]

        # Weight by level (higher levels need stronger evidence)
        level_scores: dict[ComplexityLevel, float] = {}
        all_indicators: list[str] = []

        for level, keywords in found_keywords.items():
            # Higher levels get less weight per keyword
            weight = 1.0 / (level.value + 1)
            level_scores[level] = len(keywords) * weight
            all_indicators.extend([f"{level.name}: {kw}" for kw in keywords])

        # Select level with highest score
        best_level = max(level_scores, key=lambda k: level_scores[k])

        # Calculate confidence based on number of matching keywords
        total_matches = sum(len(kws) for kws in found_keywords.values())
        confidence = min(0.9, 0.3 + (total_matches * 0.15))

        return best_level, confidence, all_indicators

    def _llm_based_assessment(self, description: str) -> tuple[ComplexityLevel, float, str, list[str]]:
        """Use LLM for complexity assessment.

        Args:
            description: Project description to analyze.

        Returns:
            Tuple of (level, confidence, reasoning, indicators).
        """
        prompt = f"""Analyze this project description and determine its complexity level:

PROJECT DESCRIPTION:
{description}

Respond with EXACTLY this format:
LEVEL: [0-4]
CONFIDENCE: [0.0-1.0]
REASONING: [one sentence explanation]
INDICATORS: [comma-separated list]"""

        response = self.chat(prompt)

        # Parse response
        level = ComplexityLevel.PRODUCT  # default
        confidence = 0.5
        reasoning = "LLM analysis"
        indicators: list[str] = []

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("LEVEL:"):
                try:
                    level_val = int(line.split(":", 1)[1].strip())
                    level = ComplexityLevel(min(4, max(0, level_val)))
                except (ValueError, IndexError):
                    pass
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                    confidence = min(1.0, max(0.0, confidence))
                except (ValueError, IndexError):
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("INDICATORS:"):
                indicators_str = line.split(":", 1)[1].strip()
                indicators = [i.strip() for i in indicators_str.split(",") if i.strip()]

        return level, confidence, reasoning, indicators

    def assess_complexity(
        self, description: str, use_llm: bool = True
    ) -> ScaleAssessment:
        """Assess project complexity from description.

        Args:
            description: Project description to analyze.
            use_llm: Whether to use LLM for assessment (default True).

        Returns:
            ScaleAssessment with recommended level and workflow.
        """
        log_agent_action(self.name, "Assessing complexity", f"Description: {description[:50]}...")

        if use_llm:
            level, confidence, reasoning, indicators = self._llm_based_assessment(description)
        else:
            level, confidence, indicators = self._keyword_based_assessment(description)
            reasoning = f"Keyword-based assessment detected {level.name} level"

        # Get recommended agents and workflow for this level
        recommended_agents = LEVEL_AGENTS.get(level, LEVEL_AGENTS[ComplexityLevel.PRODUCT])
        workflow_steps = LEVEL_WORKFLOWS.get(level, LEVEL_WORKFLOWS[ComplexityLevel.PRODUCT])
        recommended_workflow = [f"{agent.value}: {task}" for agent, task in workflow_steps]

        assessment = ScaleAssessment(
            level=level,
            confidence=confidence,
            reasoning=reasoning,
            indicators=indicators,
            recommended_agents=recommended_agents,
            recommended_workflow=recommended_workflow,
        )

        self.last_assessment = assessment

        log_agent_decision(
            self.name,
            f"Complexity: Level {level.value} ({level.name})",
            f"Confidence: {confidence:.0%}, Agents: {len(recommended_agents)}",
        )

        return assessment

    def auto_detect_level(self, project_description: str) -> ComplexityLevel:
        """Auto-detect complexity level from project description.

        This is a convenience method that returns just the level.

        Args:
            project_description: Description to analyze.

        Returns:
            Detected ComplexityLevel.
        """
        assessment = self.assess_complexity(project_description)
        return assessment.level

    def get_workflow_for_level(
        self, level: ComplexityLevel
    ) -> list[tuple[AgentType, str]]:
        """Get the recommended workflow for a complexity level.

        Args:
            level: The complexity level.

        Returns:
            List of (agent_type, task_description) tuples.
        """
        return LEVEL_WORKFLOWS.get(level, LEVEL_WORKFLOWS[ComplexityLevel.PRODUCT])

    def get_agents_for_level(self, level: ComplexityLevel) -> list[AgentType]:
        """Get the recommended agents for a complexity level.

        Args:
            level: The complexity level.

        Returns:
            List of agent types to involve.
        """
        return LEVEL_AGENTS.get(level, LEVEL_AGENTS[ComplexityLevel.PRODUCT])

    def adjust_workflow(
        self,
        base_level: ComplexityLevel,
        add_agents: list[AgentType] | None = None,
        remove_agents: list[AgentType] | None = None,
    ) -> list[tuple[AgentType, str]]:
        """Adjust the workflow for a level by adding or removing agents.

        Args:
            base_level: Starting complexity level.
            add_agents: Agents to add to the workflow.
            remove_agents: Agents to remove from the workflow.

        Returns:
            Adjusted workflow steps.
        """
        workflow = list(LEVEL_WORKFLOWS.get(base_level, LEVEL_WORKFLOWS[ComplexityLevel.PRODUCT]))

        # Remove specified agents
        if remove_agents:
            workflow = [(agent, task) for agent, task in workflow if agent not in remove_agents]

        # Add specified agents (at the end)
        if add_agents:
            for agent in add_agents:
                if not any(a == agent for a, _ in workflow):
                    # Add with generic task description
                    task_map = {
                        AgentType.PRODUCT_MANAGER: "Requirements analysis",
                        AgentType.ARCHITECT: "Technical design",
                        AgentType.UX_DESIGNER: "UX review",
                        AgentType.DEVELOPER: "Implementation",
                        AgentType.QA_TESTER: "Testing",
                        AgentType.SCRUM_MASTER: "Coordination",
                    }
                    workflow.append((agent, task_map.get(agent, "Task execution")))

        return workflow

    def get_scale_summary(self) -> str:
        """Get a summary of scale levels and their workflows.

        Returns:
            Formatted string describing all scale levels.
        """
        lines = ["=== MAT Scale Levels ===", ""]

        for level in ComplexityLevel:
            agents = LEVEL_AGENTS.get(level, [])
            workflow = LEVEL_WORKFLOWS.get(level, [])

            lines.append(f"Level {level.value}: {level.name}")
            lines.append(f"  Agents: {', '.join(a.value for a in agents)}")
            lines.append(f"  Steps: {len(workflow)}")
            lines.append("")

        return "\n".join(lines)
