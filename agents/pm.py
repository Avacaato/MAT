"""Product Manager Agent for MAT.

The ProductManagerAgent conducts discovery interviews to gather project requirements.
It asks questions about problems, users, features, success criteria, and scope,
then summarizes findings for confirmation.
"""

from dataclasses import dataclass, field
from enum import Enum

from agents.base import BaseAgent
from llm.client import OllamaClient


class DiscoveryPhase(Enum):
    """Phases of the discovery interview."""

    PROBLEM = "problem"
    USERS = "users"
    FEATURES = "features"
    SUCCESS = "success"
    SCOPE = "scope"
    SUMMARY = "summary"
    COMPLETE = "complete"


# Discovery questions for each phase
DISCOVERY_QUESTIONS: dict[DiscoveryPhase, str] = {
    DiscoveryPhase.PROBLEM: (
        "What specific problem does this solve? "
        "What happens if this doesn't exist?"
    ),
    DiscoveryPhase.USERS: (
        "Who exactly will use this? Be specific - "
        "is it you, customers, employees, everyone?"
    ),
    DiscoveryPhase.FEATURES: (
        "If this could only do 3 things, what would they be?"
    ),
    DiscoveryPhase.SUCCESS: (
        "How will you know this is working? "
        "What does success look like?"
    ),
    DiscoveryPhase.SCOPE: (
        "What should this explicitly NOT do? "
        "What's out of scope for now?"
    ),
}


PM_SYSTEM_PROMPT = """You are a Product Manager agent conducting discovery interviews.

Your role is to:
1. Understand the problem the user wants to solve
2. Identify who will use the solution
3. Define core features and requirements
4. Establish success criteria
5. Clarify what is out of scope

Guidelines:
- Ask clarifying questions when answers are vague
- Push for specifics - if they say "users can manage things", ask "what things? how?"
- Be concise but thorough
- Summarize findings accurately

When asked to summarize, provide a clear, structured summary of:
- Problem statement
- Target users
- Core features (top 3)
- Success metrics
- Out of scope items"""


@dataclass
class DiscoveryFindings:
    """Collected findings from the discovery interview."""

    problem: str = ""
    users: str = ""
    features: str = ""
    success: str = ""
    scope: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert findings to a dictionary."""
        return {
            "problem": self.problem,
            "users": self.users,
            "features": self.features,
            "success": self.success,
            "scope": self.scope,
        }

    def is_complete(self) -> bool:
        """Check if all findings have been gathered."""
        return all([
            self.problem,
            self.users,
            self.features,
            self.success,
            self.scope,
        ])


@dataclass
class ProductManagerAgent(BaseAgent):
    """Product Manager agent that conducts discovery interviews.

    Attributes:
        current_phase: Current phase of the discovery interview.
        findings: Collected findings from the interview.
    """

    name: str = field(default="Product Manager")
    role: str = field(default="Conduct discovery interviews and gather requirements")
    system_prompt: str = field(default=PM_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    current_phase: DiscoveryPhase = field(default=DiscoveryPhase.PROBLEM)
    findings: DiscoveryFindings = field(default_factory=DiscoveryFindings)

    def get_current_question(self) -> str | None:
        """Get the question for the current phase.

        Returns:
            The question string, or None if in summary/complete phase.
        """
        return DISCOVERY_QUESTIONS.get(self.current_phase)

    def _advance_phase(self) -> None:
        """Advance to the next discovery phase."""
        phase_order = [
            DiscoveryPhase.PROBLEM,
            DiscoveryPhase.USERS,
            DiscoveryPhase.FEATURES,
            DiscoveryPhase.SUCCESS,
            DiscoveryPhase.SCOPE,
            DiscoveryPhase.SUMMARY,
            DiscoveryPhase.COMPLETE,
        ]
        current_idx = phase_order.index(self.current_phase)
        if current_idx < len(phase_order) - 1:
            self.current_phase = phase_order[current_idx + 1]

    def _store_response(self, response: str) -> None:
        """Store the user's response for the current phase.

        Args:
            response: The user's response to store.
        """
        phase_to_field = {
            DiscoveryPhase.PROBLEM: "problem",
            DiscoveryPhase.USERS: "users",
            DiscoveryPhase.FEATURES: "features",
            DiscoveryPhase.SUCCESS: "success",
            DiscoveryPhase.SCOPE: "scope",
        }
        field_name = phase_to_field.get(self.current_phase)
        if field_name:
            setattr(self.findings, field_name, response)

    def process_response(self, user_response: str) -> str:
        """Process a user's response and return the next question or summary.

        This is the main method for conducting the interview. It:
        1. Stores the user's response for the current phase
        2. Uses the LLM to analyze if the response needs clarification
        3. Advances to the next phase or asks for clarification
        4. Returns the next question or generates a summary

        Args:
            user_response: The user's response to the current question.

        Returns:
            The next question, a clarification request, or the summary.
        """
        if self.current_phase == DiscoveryPhase.COMPLETE:
            return "Discovery interview is complete. Call get_summary() for findings."

        # For summary phase, generate and return the summary
        if self.current_phase == DiscoveryPhase.SUMMARY:
            summary = self.generate_summary()
            self._advance_phase()
            return summary

        # Store the response
        self._store_response(user_response)

        # Check if response needs clarification using LLM
        clarification_prompt = (
            f"The user was asked: '{self.get_current_question()}'\n"
            f"They responded: '{user_response}'\n\n"
            "Is this response specific and actionable enough? "
            "If yes, respond with exactly 'SUFFICIENT'. "
            "If no, ask ONE specific follow-up question to clarify."
        )

        llm_response = self.chat(clarification_prompt)

        if "SUFFICIENT" in llm_response.upper():
            # Response is good, advance to next phase
            self._advance_phase()
            next_question = self.get_current_question()
            if next_question:
                return next_question
            # We're at summary phase
            summary = self.generate_summary()
            self._advance_phase()
            return summary
        else:
            # LLM wants clarification - return its follow-up question
            return llm_response

    def generate_summary(self) -> str:
        """Generate a summary of the discovery findings.

        Uses the LLM to create a structured summary based on collected findings.

        Returns:
            A formatted summary string.
        """
        summary_prompt = (
            "Based on these discovery findings, provide a clear summary:\n\n"
            f"Problem: {self.findings.problem}\n"
            f"Users: {self.findings.users}\n"
            f"Core Features: {self.findings.features}\n"
            f"Success Criteria: {self.findings.success}\n"
            f"Out of Scope: {self.findings.scope}\n\n"
            "Format the summary as:\n"
            "---\n"
            "PROBLEM: [one sentence]\n"
            "USERS: [specific user types]\n"
            "FEATURES:\n"
            "1. [feature 1]\n"
            "2. [feature 2]\n"
            "3. [feature 3]\n"
            "SUCCESS: [measurable criteria]\n"
            "OUT OF SCOPE: [exclusions]\n"
            "---\n\n"
            "End with: 'Does this capture your project correctly?'"
        )

        return self.chat(summary_prompt)

    def get_findings(self) -> dict[str, str]:
        """Get the collected findings as a dictionary.

        Returns:
            Dictionary with problem, users, features, success, scope.
        """
        return self.findings.to_dict()

    def is_interview_complete(self) -> bool:
        """Check if the discovery interview is complete.

        Returns:
            True if all phases have been completed.
        """
        return self.current_phase == DiscoveryPhase.COMPLETE

    def reset_interview(self) -> None:
        """Reset the interview to start fresh."""
        self.current_phase = DiscoveryPhase.PROBLEM
        self.findings = DiscoveryFindings()
        self.clear_history()

    def start_interview(self) -> str:
        """Start the discovery interview.

        Returns:
            The opening message and first question.
        """
        self.reset_interview()
        return (
            "Let's start the discovery interview. "
            "I'll ask you a few questions to understand your project.\n\n"
            f"{self.get_current_question()}"
        )
