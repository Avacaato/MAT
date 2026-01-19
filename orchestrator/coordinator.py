"""Agent Orchestrator for MAT.

The AgentOrchestrator coordinates multiple agents to work together on tasks.
It routes tasks to appropriate agents, passes context between them, and
manages the overall conversation flow.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.base import BaseAgent
from agents.pm import ProductManagerAgent
from agents.architect import ArchitectAgent
from agents.developer import DeveloperAgent, UserStory
from agents.ux import UXDesignerAgent
from agents.scrum_master import ScrumMasterAgent
from agents.qa import QATesterAgent
from llm.client import OllamaClient
from utils.logger import log_agent_action, log_agent_decision


class AgentType(Enum):
    """Types of agents available in MAT."""

    PRODUCT_MANAGER = "product_manager"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    UX_DESIGNER = "ux_designer"
    SCRUM_MASTER = "scrum_master"
    QA_TESTER = "qa_tester"


@dataclass
class TaskContext:
    """Context passed between agents during task execution.

    Attributes:
        task_type: The type of task being executed.
        description: Human-readable description of the task.
        data: Arbitrary data dictionary for passing between agents.
        previous_agent: The agent that last worked on this context.
        history: List of (agent_type, summary) tuples tracking agent contributions.
    """

    task_type: str
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    previous_agent: AgentType | None = None
    history: list[tuple[AgentType, str]] = field(default_factory=list)

    def add_to_history(self, agent_type: AgentType, summary: str) -> None:
        """Add an agent's contribution to the history.

        Args:
            agent_type: The type of agent that contributed.
            summary: Summary of what the agent did.
        """
        self.history.append((agent_type, summary))
        self.previous_agent = agent_type

    def get_context_summary(self) -> str:
        """Get a summary of all agent contributions.

        Returns:
            Formatted string with all agent contributions.
        """
        if not self.history:
            return "No previous context."

        lines = ["Previous agent contributions:"]
        for agent_type, summary in self.history:
            lines.append(f"  - {agent_type.value}: {summary}")
        return "\n".join(lines)


@dataclass
class TaskResult:
    """Result of a task execution.

    Attributes:
        success: Whether the task completed successfully.
        message: Human-readable result message.
        data: Any data produced by the task.
        errors: List of error messages if any occurred.
    """

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "errors": self.errors,
        }


# Task type to agent type mappings for routing
TASK_ROUTING: dict[str, list[AgentType]] = {
    "discovery": [AgentType.PRODUCT_MANAGER],
    "requirements": [AgentType.PRODUCT_MANAGER],
    "architecture": [AgentType.ARCHITECT],
    "design": [AgentType.UX_DESIGNER, AgentType.ARCHITECT],
    "implementation": [AgentType.DEVELOPER],
    "development": [AgentType.DEVELOPER],
    "testing": [AgentType.QA_TESTER],
    "verification": [AgentType.QA_TESTER],
    "planning": [AgentType.SCRUM_MASTER],
    "status": [AgentType.SCRUM_MASTER],
    "full_build": [
        AgentType.PRODUCT_MANAGER,
        AgentType.ARCHITECT,
        AgentType.UX_DESIGNER,
        AgentType.DEVELOPER,
        AgentType.QA_TESTER,
    ],
}


ORCHESTRATOR_SYSTEM_PROMPT = """You are an Orchestrator agent coordinating a team of specialized agents.

Your responsibilities:
1. Analyze incoming tasks and route them to appropriate agents
2. Pass context between agents for continuity
3. Manage the overall conversation and workflow
4. Ensure tasks are completed successfully

Available agents:
- Product Manager: Discovery interviews, requirements gathering
- Architect: Technical design, architecture decisions
- UX Designer: User interface design, user flows
- Developer: Code implementation
- QA Tester: Testing and verification
- Scrum Master: Workflow management, status tracking

Guidelines:
- Route tasks to the most appropriate agent based on task type
- Provide clear context when handing off between agents
- Keep track of progress and summarize results
- Escalate issues when agents get stuck"""


@dataclass
class AgentOrchestrator(BaseAgent):
    """Orchestrator that coordinates multiple agents.

    Routes tasks to appropriate agents, passes context between them,
    and manages the overall conversation flow.

    Attributes:
        pm_agent: Product Manager agent instance.
        architect_agent: Architect agent instance.
        developer_agent: Developer agent instance.
        ux_agent: UX Designer agent instance.
        scrum_master_agent: Scrum Master agent instance.
        qa_agent: QA Tester agent instance.
        current_context: Current task context being worked on.
    """

    name: str = field(default="Orchestrator")
    role: str = field(default="Coordinate multiple agents on tasks")
    system_prompt: str = field(default=ORCHESTRATOR_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    pm_agent: ProductManagerAgent = field(default_factory=ProductManagerAgent)
    architect_agent: ArchitectAgent = field(default_factory=ArchitectAgent)
    developer_agent: DeveloperAgent = field(default_factory=DeveloperAgent)
    ux_agent: UXDesignerAgent = field(default_factory=UXDesignerAgent)
    scrum_master_agent: ScrumMasterAgent = field(default_factory=ScrumMasterAgent)
    qa_agent: QATesterAgent = field(default_factory=QATesterAgent)
    current_context: TaskContext | None = field(default=None)

    def get_agent(self, agent_type: AgentType) -> BaseAgent:
        """Get an agent instance by type.

        Args:
            agent_type: The type of agent to retrieve.

        Returns:
            The agent instance.

        Raises:
            ValueError: If the agent type is unknown.
        """
        agent_map: dict[AgentType, BaseAgent] = {
            AgentType.PRODUCT_MANAGER: self.pm_agent,
            AgentType.ARCHITECT: self.architect_agent,
            AgentType.DEVELOPER: self.developer_agent,
            AgentType.UX_DESIGNER: self.ux_agent,
            AgentType.SCRUM_MASTER: self.scrum_master_agent,
            AgentType.QA_TESTER: self.qa_agent,
        }
        agent = agent_map.get(agent_type)
        if agent is None:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return agent

    def determine_agent_for_task(self, task_type: str) -> list[AgentType]:
        """Determine which agents should handle a task.

        Args:
            task_type: The type of task (e.g., "discovery", "implementation").

        Returns:
            List of agent types that should handle the task.
        """
        task_type_lower = task_type.lower()

        # Check direct mapping first
        if task_type_lower in TASK_ROUTING:
            return TASK_ROUTING[task_type_lower]

        # Check for partial matches
        for key, routed_agents in TASK_ROUTING.items():
            if key in task_type_lower or task_type_lower in key:
                return routed_agents

        # Use LLM to determine routing if no direct match
        routing_prompt = (
            f"Given a task of type '{task_type}', which agent(s) should handle it?\n\n"
            "Available agents:\n"
            "- PRODUCT_MANAGER: Discovery, requirements, user needs\n"
            "- ARCHITECT: Technical design, architecture\n"
            "- DEVELOPER: Code implementation\n"
            "- UX_DESIGNER: UI/UX design, user flows\n"
            "- SCRUM_MASTER: Workflow, planning, status\n"
            "- QA_TESTER: Testing, verification\n\n"
            "Respond with ONLY the agent names in order, comma-separated.\n"
            "Example: DEVELOPER, QA_TESTER"
        )

        response = self.chat(routing_prompt)

        # Parse response into agent types
        parsed_agents: list[AgentType] = []
        for part in response.upper().split(","):
            part = part.strip()
            for agent_type in AgentType:
                if agent_type.value.upper() == part or agent_type.name == part:
                    parsed_agents.append(agent_type)
                    break

        if not parsed_agents:
            # Default to developer for unknown tasks
            log_agent_decision(
                self.name,
                f"Unknown task type '{task_type}', defaulting to Developer",
                f"LLM response: {response}",
            )
            return [AgentType.DEVELOPER]

        return parsed_agents

    def create_context(self, task_type: str, description: str = "") -> TaskContext:
        """Create a new task context.

        Args:
            task_type: The type of task.
            description: Description of the task.

        Returns:
            New TaskContext instance.
        """
        context = TaskContext(task_type=task_type, description=description)
        self.current_context = context
        log_agent_action(self.name, "Created context", f"Type: {task_type}")
        return context

    def pass_context_to_agent(
        self, agent_type: AgentType, context: TaskContext
    ) -> str:
        """Format context for passing to an agent.

        Args:
            agent_type: The agent receiving the context.
            context: The task context to pass.

        Returns:
            Formatted context string for the agent.
        """
        context_str = (
            f"Task: {context.task_type}\n"
            f"Description: {context.description}\n\n"
        )

        if context.data:
            context_str += "Data:\n"
            for key, value in context.data.items():
                context_str += f"  {key}: {value}\n"
            context_str += "\n"

        context_str += context.get_context_summary()

        log_agent_action(
            self.name,
            "Passing context",
            f"To: {agent_type.value}",
        )

        return context_str

    def route_to_agent(
        self, agent_type: AgentType, message: str, context: TaskContext | None = None
    ) -> str:
        """Route a message to a specific agent.

        Args:
            agent_type: The agent to route to.
            message: The message to send.
            context: Optional context to include.

        Returns:
            The agent's response.
        """
        agent = self.get_agent(agent_type)

        # Prepare message with context if provided
        if context:
            context_str = self.pass_context_to_agent(agent_type, context)
            full_message = f"{context_str}\n\n{message}"
        else:
            full_message = message

        log_agent_action(
            self.name, "Routing to agent", f"{agent_type.value}: {message[:50]}..."
        )

        response = agent.chat(full_message)

        # Update context history if available
        if context:
            context.add_to_history(agent_type, f"Processed: {message[:30]}...")

        return response

    def execute_task(
        self, task_type: str, message: str, description: str = ""
    ) -> TaskResult:
        """Execute a task by routing to appropriate agent(s).

        Args:
            task_type: The type of task to execute.
            message: The task message/instruction.
            description: Optional task description.

        Returns:
            TaskResult with success status and data.
        """
        # Create context
        context = self.create_context(task_type, description or message)

        # Determine routing
        agents = self.determine_agent_for_task(task_type)
        log_agent_decision(
            self.name,
            f"Task '{task_type}' routed to {len(agents)} agent(s)",
            f"Agents: {[a.value for a in agents]}",
        )

        results: list[str] = []
        errors: list[str] = []

        # Route to each agent in sequence
        for agent_type in agents:
            try:
                response = self.route_to_agent(agent_type, message, context)
                results.append(f"{agent_type.value}: {response}")
                context.data[f"{agent_type.value}_response"] = response
            except Exception as e:
                error_msg = f"{agent_type.value}: {str(e)}"
                errors.append(error_msg)
                log_agent_action(self.name, "Agent error", error_msg)

        success = len(errors) == 0
        message_result = "\n\n".join(results) if results else "No results"

        return TaskResult(
            success=success,
            message=message_result,
            data=context.data,
            errors=errors,
        )

    def execute_workflow(
        self, workflow_steps: list[tuple[AgentType, str]]
    ) -> TaskResult:
        """Execute a predefined workflow with multiple steps.

        Args:
            workflow_steps: List of (agent_type, message) tuples defining the workflow.

        Returns:
            TaskResult with combined results.
        """
        if not workflow_steps:
            return TaskResult(
                success=False,
                message="No workflow steps provided",
                errors=["Empty workflow"],
            )

        # Create context for workflow
        context = self.create_context("workflow", f"{len(workflow_steps)} steps")

        results: dict[str, str] = {}
        errors: list[str] = []

        for i, (agent_type, message) in enumerate(workflow_steps, 1):
            step_name = f"step_{i}_{agent_type.value}"
            log_agent_action(
                self.name,
                f"Workflow step {i}/{len(workflow_steps)}",
                f"Agent: {agent_type.value}",
            )

            try:
                response = self.route_to_agent(agent_type, message, context)
                results[step_name] = response
                context.data[step_name] = response
            except Exception as e:
                error_msg = f"Step {i} ({agent_type.value}): {str(e)}"
                errors.append(error_msg)
                log_agent_action(self.name, "Workflow step failed", error_msg)
                # Continue with remaining steps

        success = len(errors) == 0

        return TaskResult(
            success=success,
            message=f"Completed {len(results)}/{len(workflow_steps)} steps",
            data=results,
            errors=errors,
        )

    def implement_story(self, story_data: dict[str, Any]) -> TaskResult:
        """Implement a user story using Developer and QA agents.

        This is a convenience method for the common implement-and-verify pattern.

        Args:
            story_data: Story data in prd.json format.

        Returns:
            TaskResult with implementation results.
        """
        story = UserStory.from_dict(story_data)

        # Create context
        context = self.create_context("implementation", story.title)
        context.data["story_id"] = story.id
        context.data["acceptance_criteria"] = story.acceptance_criteria

        # Implementation phase
        log_agent_action(self.name, "Implementing story", f"{story.id} - {story.title}")
        try:
            written_files = self.developer_agent.implement_story(story)
            context.data["written_files"] = written_files
            context.add_to_history(
                AgentType.DEVELOPER,
                f"Wrote {len(written_files)} files",
            )
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Implementation failed: {str(e)}",
                data=context.data,
                errors=[str(e)],
            )

        # Verification phase
        log_agent_action(self.name, "Verifying story", story.id)
        try:
            verification_report = self.qa_agent.verify_story(story_data, written_files)
            context.data["verification"] = {
                "passed": verification_report.overall_passed,
                "details": verification_report.to_markdown(),
            }
            context.add_to_history(
                AgentType.QA_TESTER,
                f"Verification: {'PASSED' if verification_report.overall_passed else 'FAILED'}",
            )

            return TaskResult(
                success=verification_report.overall_passed,
                message=(
                    f"Story {story.id} implemented and verified"
                    if verification_report.overall_passed
                    else f"Story {story.id} failed verification"
                ),
                data=context.data,
                errors=[] if verification_report.overall_passed else ["Verification failed"],
            )
        except Exception as e:
            return TaskResult(
                success=False,
                message=f"Verification failed: {str(e)}",
                data=context.data,
                errors=[str(e)],
            )

    def get_status(self) -> str:
        """Get the current orchestrator status.

        Returns:
            Status string with agent and context information.
        """
        lines = ["=== Orchestrator Status ==="]

        # List all agents
        lines.append("\nAgents:")
        for agent_type in AgentType:
            agent = self.get_agent(agent_type)
            history_summary = agent.get_history_summary()
            lines.append(f"  - {agent_type.value}: {history_summary}")

        # Current context
        if self.current_context:
            lines.append(f"\nCurrent Task: {self.current_context.task_type}")
            lines.append(f"Description: {self.current_context.description}")
            lines.append(f"History entries: {len(self.current_context.history)}")
        else:
            lines.append("\nNo active task context")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all agents and context."""
        self.current_context = None
        self.clear_history()

        # Reset all agents
        for agent_type in AgentType:
            agent = self.get_agent(agent_type)
            agent.clear_history()

        log_agent_action(self.name, "Reset", "All agents and context cleared")
