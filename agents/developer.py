"""Developer Agent for MAT.

The DeveloperAgent writes code to implement user stories.
It reads user stories, generates code that satisfies acceptance criteria,
and uses file_ops to read context and write implementations.
"""

from dataclasses import dataclass, field
from typing import Any

from agents.base import BaseAgent
from llm.client import OllamaClient
from utils.file_ops import list_files, read_file, write_file


DEVELOPER_SYSTEM_PROMPT = """You are a Software Developer agent implementing code for user stories.

Your role is to:
1. Read and understand user stories with their acceptance criteria
2. Analyze existing code for context and patterns
3. Generate code that satisfies all acceptance criteria
4. Follow existing code conventions and patterns

Guidelines:
- Write clean, readable, and maintainable code
- Follow the existing code style and patterns
- Include type hints for Python code
- Handle errors appropriately
- Keep implementations simple and focused
- Only implement what is required by the acceptance criteria

When writing code:
- Use consistent naming conventions
- Add docstrings for public functions and classes
- Import dependencies correctly
- Consider edge cases mentioned in acceptance criteria

Output code in code blocks with the filename as a comment on the first line."""


@dataclass
class UserStory:
    """Represents a user story to implement."""

    id: str
    title: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserStory":
        """Create a UserStory from a dictionary.

        Args:
            data: Dictionary with story data (from prd.json format).

        Returns:
            A UserStory instance.
        """
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptanceCriteria", []),
        )

    def to_prompt(self) -> str:
        """Format the user story for an LLM prompt.

        Returns:
            Formatted string representation of the story.
        """
        criteria_list = "\n".join(f"- {c}" for c in self.acceptance_criteria)
        return (
            f"User Story: {self.id} - {self.title}\n\n"
            f"Description: {self.description}\n\n"
            f"Acceptance Criteria:\n{criteria_list}"
        )


@dataclass
class CodeFile:
    """Represents a code file to be written."""

    path: str
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary format."""
        return {"path": self.path, "content": self.content}


@dataclass
class ImplementationPlan:
    """Plan for implementing a user story."""

    story_id: str
    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    approach: str = ""


@dataclass
class DeveloperAgent(BaseAgent):
    """Developer agent that implements user stories.

    Attributes:
        current_story: The user story currently being implemented.
        context_files: Files read for context during implementation.
    """

    name: str = field(default="Developer")
    role: str = field(default="Implement code for user stories")
    system_prompt: str = field(default=DEVELOPER_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    current_story: UserStory | None = field(default=None)
    context_files: dict[str, str] = field(default_factory=dict)

    def set_story(self, story: UserStory) -> None:
        """Set the current user story to implement.

        Args:
            story: The user story to implement.
        """
        self.current_story = story
        self.context_files.clear()
        self.clear_history()

    def read_context_file(self, path: str) -> str:
        """Read a file for context during implementation.

        Args:
            path: Path to the file (relative to project directory).

        Returns:
            File contents, or empty string if file doesn't exist.
        """
        content = read_file(path)
        if content:
            self.context_files[path] = content
        return content

    def read_context_files(self, paths: list[str]) -> dict[str, str]:
        """Read multiple files for context.

        Args:
            paths: List of file paths to read.

        Returns:
            Dictionary mapping paths to contents.
        """
        for path in paths:
            self.read_context_file(path)
        return self.context_files

    def find_related_files(self, pattern: str = "**/*.py") -> list[str]:
        """Find files matching a pattern.

        Args:
            pattern: Glob pattern to match (default: all Python files).

        Returns:
            List of matching file paths as strings.
        """
        files = list_files(".", pattern)
        return [str(f) for f in files]

    def _format_context(self) -> str:
        """Format loaded context files for prompts.

        Returns:
            Formatted string with file contents.
        """
        if not self.context_files:
            return "No context files loaded."

        sections = []
        for path, content in self.context_files.items():
            sections.append(f"--- {path} ---\n{content}")
        return "\n\n".join(sections)

    def analyze_story(self) -> ImplementationPlan:
        """Analyze the current story and create an implementation plan.

        Returns:
            An ImplementationPlan with files to create/modify and approach.

        Raises:
            ValueError: If no story is set.
        """
        if not self.current_story:
            raise ValueError("No user story set. Call set_story() first.")

        prompt = (
            f"Analyze this user story and determine what needs to be implemented:\n\n"
            f"{self.current_story.to_prompt()}\n\n"
            "Respond in this exact format:\n"
            "FILES_TO_CREATE: [comma-separated list of file paths, or 'None']\n"
            "FILES_TO_MODIFY: [comma-separated list of file paths, or 'None']\n"
            "APPROACH: [1-2 sentences describing the implementation approach]"
        )

        response = self.chat(prompt)
        return self._parse_plan_response(response)

    def _parse_plan_response(self, response: str) -> ImplementationPlan:
        """Parse LLM response into an ImplementationPlan.

        Args:
            response: The raw LLM response.

        Returns:
            Parsed ImplementationPlan.
        """
        plan = ImplementationPlan(
            story_id=self.current_story.id if self.current_story else ""
        )

        for line in response.strip().split("\n"):
            line_upper = line.upper()
            if line_upper.startswith("FILES_TO_CREATE:"):
                files_str = line.split(":", 1)[1].strip()
                if files_str.lower() != "none":
                    plan.files_to_create = [f.strip() for f in files_str.split(",")]
            elif line_upper.startswith("FILES_TO_MODIFY:"):
                files_str = line.split(":", 1)[1].strip()
                if files_str.lower() != "none":
                    plan.files_to_modify = [f.strip() for f in files_str.split(",")]
            elif line_upper.startswith("APPROACH:"):
                plan.approach = line.split(":", 1)[1].strip()

        return plan

    def generate_code(self, file_path: str) -> CodeFile:
        """Generate code for a specific file.

        Args:
            file_path: The path of the file to generate.

        Returns:
            A CodeFile with the generated content.

        Raises:
            ValueError: If no story is set.
        """
        if not self.current_story:
            raise ValueError("No user story set. Call set_story() first.")

        context_str = self._format_context()

        prompt = (
            f"Generate the code for file '{file_path}' to implement this user story:\n\n"
            f"{self.current_story.to_prompt()}\n\n"
            f"Existing code context:\n{context_str}\n\n"
            "Requirements:\n"
            "- Write complete, working code\n"
            "- Follow existing patterns from the context\n"
            "- Include all necessary imports\n"
            "- Add docstrings and type hints\n"
            "- Satisfy all acceptance criteria\n\n"
            "Output ONLY the code, no explanations. Start with the first line of code."
        )

        response = self.chat(prompt)
        # Clean up the response - remove markdown code blocks if present
        code = self._extract_code(response)
        return CodeFile(path=file_path, content=code)

    def _extract_code(self, response: str) -> str:
        """Extract code from LLM response, handling markdown code blocks.

        Args:
            response: The raw LLM response.

        Returns:
            Clean code content.
        """
        code = response.strip()

        # Remove markdown code blocks if present
        if code.startswith("```"):
            lines = code.split("\n")
            # Remove first line (```python or similar)
            lines = lines[1:]
            # Find and remove closing ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines)

        return code

    def modify_code(self, file_path: str, existing_content: str) -> CodeFile:
        """Modify existing code for a file.

        Args:
            file_path: The path of the file to modify.
            existing_content: The current content of the file.

        Returns:
            A CodeFile with the modified content.

        Raises:
            ValueError: If no story is set.
        """
        if not self.current_story:
            raise ValueError("No user story set. Call set_story() first.")

        context_str = self._format_context()

        prompt = (
            f"Modify the file '{file_path}' to implement this user story:\n\n"
            f"{self.current_story.to_prompt()}\n\n"
            f"Current file content:\n```\n{existing_content}\n```\n\n"
            f"Other code context:\n{context_str}\n\n"
            "Requirements:\n"
            "- Preserve existing functionality unless it conflicts\n"
            "- Follow existing patterns and style\n"
            "- Add new code to satisfy acceptance criteria\n"
            "- Keep changes minimal and focused\n\n"
            "Output ONLY the complete modified file, no explanations."
        )

        response = self.chat(prompt)
        code = self._extract_code(response)
        return CodeFile(path=file_path, content=code)

    def write_code_file(self, code_file: CodeFile) -> str:
        """Write a code file to the project.

        Args:
            code_file: The CodeFile to write.

        Returns:
            The path where the file was written.
        """
        result_path = write_file(code_file.path, code_file.content)
        return str(result_path)

    def implement_story(self, story: UserStory) -> list[str]:
        """Implement a complete user story.

        This method orchestrates the full implementation process:
        1. Sets the story
        2. Analyzes and plans the implementation
        3. Reads context files
        4. Generates/modifies code
        5. Writes files

        Args:
            story: The user story to implement.

        Returns:
            List of file paths that were written.
        """
        self.set_story(story)

        # Analyze and plan
        plan = self.analyze_story()

        # Read files to modify for context
        for file_path in plan.files_to_modify:
            self.read_context_file(file_path)

        # Find and read some related files for context
        related = self.find_related_files("**/*.py")
        # Limit to first 5 files to avoid context overflow
        for file_path in related[:5]:
            if file_path not in self.context_files:
                self.read_context_file(file_path)

        written_files: list[str] = []

        # Generate new files
        for file_path in plan.files_to_create:
            code_file = self.generate_code(file_path)
            written_path = self.write_code_file(code_file)
            written_files.append(written_path)

        # Modify existing files
        for file_path in plan.files_to_modify:
            existing_content = self.context_files.get(file_path, "")
            code_file = self.modify_code(file_path, existing_content)
            written_path = self.write_code_file(code_file)
            written_files.append(written_path)

        return written_files

    def get_implementation_summary(self) -> str:
        """Get a summary of the current implementation state.

        Returns:
            Summary string with story and context file information.
        """
        if not self.current_story:
            return "No story currently set."

        context_files = list(self.context_files.keys()) if self.context_files else []
        return (
            f"Implementing: {self.current_story.id} - {self.current_story.title}\n"
            f"Context files loaded: {len(context_files)}\n"
            f"Files: {', '.join(context_files) if context_files else 'None'}"
        )
