"""QA Tester Agent for MAT.

The QATesterAgent verifies implementations against acceptance criteria,
runs type checks and linting, and reports pass/fail status with details.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import subprocess

from agents.base import BaseAgent
from llm.client import OllamaClient
from utils.file_ops import list_files, read_file
from utils.logger import log_agent_action, log_agent_decision


class VerificationStatus(Enum):
    """Status of a verification check."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class CriterionResult:
    """Result of verifying a single acceptance criterion."""

    criterion: str
    status: VerificationStatus
    details: str = ""
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "criterion": self.criterion,
            "status": self.status.value,
            "details": self.details,
            "evidence": self.evidence,
        }


@dataclass
class TypeCheckResult:
    """Result of running type checks."""

    passed: bool
    output: str
    error_count: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "passed": self.passed,
            "output": self.output,
            "error_count": self.error_count,
            "errors": self.errors,
        }


@dataclass
class LintResult:
    """Result of running linting."""

    passed: bool
    output: str
    warning_count: int = 0
    error_count: int = 0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "passed": self.passed,
            "output": self.output,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "issues": self.issues,
        }


@dataclass
class VerificationReport:
    """Complete verification report for a story."""

    story_id: str
    story_title: str
    overall_passed: bool
    criteria_results: list[CriterionResult] = field(default_factory=list)
    type_check: TypeCheckResult | None = None
    lint_result: LintResult | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "story_id": self.story_id,
            "story_title": self.story_title,
            "overall_passed": self.overall_passed,
            "criteria_results": [cr.to_dict() for cr in self.criteria_results],
            "type_check": self.type_check.to_dict() if self.type_check else None,
            "lint_result": self.lint_result.to_dict() if self.lint_result else None,
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [
            f"# Verification Report: {self.story_id}",
            f"**Story:** {self.story_title}",
            f"**Overall Status:** {'✓ PASS' if self.overall_passed else '✗ FAIL'}",
            "",
            "## Acceptance Criteria",
        ]

        for cr in self.criteria_results:
            status_icon = {
                VerificationStatus.PASS: "✓",
                VerificationStatus.FAIL: "✗",
                VerificationStatus.SKIP: "⊘",
                VerificationStatus.ERROR: "⚠",
            }.get(cr.status, "?")
            lines.append(f"- {status_icon} {cr.criterion}")
            if cr.details:
                lines.append(f"  - {cr.details}")

        if self.type_check:
            lines.extend([
                "",
                "## Type Check",
                f"**Status:** {'✓ PASS' if self.type_check.passed else '✗ FAIL'}",
            ])
            if self.type_check.errors:
                lines.append("**Errors:**")
                for err in self.type_check.errors[:5]:  # Limit to 5 errors
                    lines.append(f"  - {err}")
                if len(self.type_check.errors) > 5:
                    lines.append(f"  - ... and {len(self.type_check.errors) - 5} more")

        if self.lint_result:
            lines.extend([
                "",
                "## Lint Check",
                f"**Status:** {'✓ PASS' if self.lint_result.passed else '✗ FAIL'}",
            ])
            if self.lint_result.issues:
                lines.append("**Issues:**")
                for issue in self.lint_result.issues[:5]:
                    lines.append(f"  - {issue}")
                if len(self.lint_result.issues) > 5:
                    lines.append(f"  - ... and {len(self.lint_result.issues) - 5} more")

        if self.summary:
            lines.extend(["", "## Summary", self.summary])

        return "\n".join(lines)


QA_TESTER_SYSTEM_PROMPT = """You are a QA Tester agent verifying software implementations.

Your responsibilities:
1. Verify that acceptance criteria are fully met
2. Check code quality and correctness
3. Identify any issues or gaps in implementation
4. Provide clear pass/fail verdicts with evidence

Guidelines:
- Be thorough but fair in verification
- Focus on the acceptance criteria as written
- Check for functional correctness, not style preferences
- Provide specific evidence for pass/fail decisions
- Note any edge cases that might be missed

When verifying acceptance criteria:
- Check if the code actually implements what's required
- Look for the specific files, functions, or features mentioned
- Verify error handling if mentioned in criteria
- Check type hints if specified

Respond in a structured format with clear PASS/FAIL verdicts."""


@dataclass
class QATesterAgent(BaseAgent):
    """QA Tester agent for verifying implementations.

    Verifies acceptance criteria, runs type checks and linting,
    and generates detailed verification reports.

    Attributes:
        current_story: The story being verified (dict from prd.json).
        changed_files: Files changed in the implementation.
    """

    name: str = field(default="QA Tester")
    role: str = field(default="Verify implementations and run quality checks")
    system_prompt: str = field(default=QA_TESTER_SYSTEM_PROMPT)
    client: OllamaClient = field(default_factory=OllamaClient)
    current_story: dict[str, Any] | None = field(default=None)
    changed_files: list[str] = field(default_factory=list)

    def set_story(
        self,
        story: dict[str, Any],
        changed_files: list[str] | None = None
    ) -> None:
        """Set the current story to verify.

        Args:
            story: Story dict from prd.json format.
            changed_files: List of files changed in implementation.
        """
        self.current_story = story
        self.changed_files = changed_files or []
        self.clear_history()
        log_agent_action(
            self.name,
            "Verifying story",
            f"{story.get('id', 'unknown')} - {story.get('title', 'untitled')}",
        )

    def verify_criterion(
        self,
        criterion: str,
        file_contents: dict[str, str]
    ) -> CriterionResult:
        """Verify a single acceptance criterion.

        Uses the LLM to analyze if the criterion is satisfied.

        Args:
            criterion: The acceptance criterion to verify.
            file_contents: Dict mapping file paths to their contents.

        Returns:
            CriterionResult with pass/fail status and details.
        """
        # Format file contents for prompt
        files_str = ""
        for path, content in file_contents.items():
            files_str += f"\n--- {path} ---\n{content}\n"

        prompt = f"""Verify if this acceptance criterion is met:

CRITERION: {criterion}

FILES TO CHECK:
{files_str}

Respond in this exact format:
STATUS: [PASS/FAIL/SKIP]
DETAILS: [one line explanation]
EVIDENCE: [specific code or feature that satisfies/violates the criterion]

Use SKIP only if the criterion cannot be verified from the provided files."""

        response = self.chat(prompt)

        # Parse response
        status = VerificationStatus.FAIL
        details = ""
        evidence = ""

        for line in response.strip().split("\n"):
            if line.upper().startswith("STATUS:"):
                status_str = line.split(":", 1)[1].strip().upper()
                if status_str == "PASS":
                    status = VerificationStatus.PASS
                elif status_str == "SKIP":
                    status = VerificationStatus.SKIP
                elif status_str == "ERROR":
                    status = VerificationStatus.ERROR
                else:
                    status = VerificationStatus.FAIL
            elif line.upper().startswith("DETAILS:"):
                details = line.split(":", 1)[1].strip()
            elif line.upper().startswith("EVIDENCE:"):
                evidence = line.split(":", 1)[1].strip()

        return CriterionResult(
            criterion=criterion,
            status=status,
            details=details,
            evidence=evidence,
        )

    def run_type_check(self, path: str = ".") -> TypeCheckResult:
        """Run mypy type checking on the project.

        Args:
            path: Path to check (default: current directory).

        Returns:
            TypeCheckResult with pass/fail and error details.
        """
        log_agent_action(self.name, "Running type check", f"mypy {path}")

        try:
            result = subprocess.run(
                ["mypy", path, "--ignore-missing-imports"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            output = result.stdout + result.stderr
            errors: list[str] = []

            # Parse mypy output for errors
            for line in output.strip().split("\n"):
                if line and ": error:" in line:
                    errors.append(line.strip())

            passed = result.returncode == 0

            type_result = TypeCheckResult(
                passed=passed,
                output=output[:2000],  # Limit output size
                error_count=len(errors),
                errors=errors,
            )

            log_agent_decision(
                self.name,
                f"Type check {'passed' if passed else 'failed'}",
                f"{len(errors)} errors found",
            )

            return type_result

        except FileNotFoundError:
            log_agent_action(self.name, "Type check skipped", "mypy not found")
            return TypeCheckResult(
                passed=True,  # Don't fail if mypy isn't installed
                output="mypy not installed, skipping type check",
                error_count=0,
                errors=[],
            )
        except subprocess.TimeoutExpired:
            log_agent_action(self.name, "Type check timeout", "Exceeded 60s")
            return TypeCheckResult(
                passed=False,
                output="Type check timed out after 60 seconds",
                error_count=1,
                errors=["Timeout: type check took too long"],
            )

    def run_lint_check(self, path: str = ".") -> LintResult:
        """Run ruff linting on the project.

        Args:
            path: Path to lint (default: current directory).

        Returns:
            LintResult with pass/fail and issue details.
        """
        log_agent_action(self.name, "Running lint check", f"ruff check {path}")

        try:
            result = subprocess.run(
                ["ruff", "check", path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout + result.stderr
            issues: list[str] = []
            warning_count = 0
            error_count = 0

            # Parse ruff output
            for line in output.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("Found"):
                    issues.append(line)
                    # Ruff marks warnings/errors differently
                    if "W" in line[:20]:  # Warning code in first part
                        warning_count += 1
                    else:
                        error_count += 1

            passed = result.returncode == 0

            lint_result = LintResult(
                passed=passed,
                output=output[:2000],
                warning_count=warning_count,
                error_count=error_count,
                issues=issues,
            )

            log_agent_decision(
                self.name,
                f"Lint check {'passed' if passed else 'failed'}",
                f"{error_count} errors, {warning_count} warnings",
            )

            return lint_result

        except FileNotFoundError:
            log_agent_action(self.name, "Lint check skipped", "ruff not found")
            return LintResult(
                passed=True,  # Don't fail if ruff isn't installed
                output="ruff not installed, skipping lint check",
                warning_count=0,
                error_count=0,
                issues=[],
            )
        except subprocess.TimeoutExpired:
            log_agent_action(self.name, "Lint check timeout", "Exceeded 30s")
            return LintResult(
                passed=False,
                output="Lint check timed out after 30 seconds",
                warning_count=0,
                error_count=1,
                issues=["Timeout: lint check took too long"],
            )

    def verify_story(
        self,
        story: dict[str, Any],
        changed_files: list[str] | None = None
    ) -> VerificationReport:
        """Verify a complete user story implementation.

        This method orchestrates the full verification process:
        1. Sets the story context
        2. Reads changed files
        3. Verifies each acceptance criterion
        4. Runs type check
        5. Runs lint check
        6. Generates verification report

        Args:
            story: Story dict from prd.json format.
            changed_files: List of files changed in implementation.

        Returns:
            VerificationReport with all results.
        """
        self.set_story(story, changed_files)

        story_id = story.get("id", "unknown")
        story_title = story.get("title", "untitled")
        acceptance_criteria = story.get("acceptanceCriteria", [])

        # Read file contents for verification
        file_contents: dict[str, str] = {}
        files_to_read = changed_files or []

        # Also try to find relevant files mentioned in criteria
        for criterion in acceptance_criteria:
            # Look for patterns like `file.py` or `module/file.py`
            for word in criterion.split():
                if "/" in word or word.endswith((".py", ".js", ".ts", ".json")):
                    clean_word = word.strip("`'\"(),")
                    if clean_word and clean_word not in files_to_read:
                        files_to_read.append(clean_word)

        # Read all relevant files
        for file_path in files_to_read:
            content = read_file(file_path)
            if content:
                file_contents[file_path] = content

        # Verify each criterion
        criteria_results: list[CriterionResult] = []
        for criterion in acceptance_criteria:
            # Skip "Typecheck passes" - we verify that separately
            if criterion.lower().strip() == "typecheck passes":
                continue
            result = self.verify_criterion(criterion, file_contents)
            criteria_results.append(result)

        # Run type check
        type_check = self.run_type_check()

        # Run lint check
        lint_result = self.run_lint_check()

        # Determine overall pass/fail
        criteria_passed = all(
            cr.status in (VerificationStatus.PASS, VerificationStatus.SKIP)
            for cr in criteria_results
        )
        overall_passed = criteria_passed and type_check.passed

        # Generate summary
        summary_parts = []
        passed_count = sum(
            1 for cr in criteria_results if cr.status == VerificationStatus.PASS
        )
        failed_count = sum(
            1 for cr in criteria_results if cr.status == VerificationStatus.FAIL
        )
        summary_parts.append(
            f"Acceptance criteria: {passed_count} passed, {failed_count} failed"
        )
        summary_parts.append(
            f"Type check: {'passed' if type_check.passed else 'failed'}"
        )
        summary_parts.append(
            f"Lint check: {'passed' if lint_result.passed else 'failed (warnings only)'}"
        )

        report = VerificationReport(
            story_id=story_id,
            story_title=story_title,
            overall_passed=overall_passed,
            criteria_results=criteria_results,
            type_check=type_check,
            lint_result=lint_result,
            summary=". ".join(summary_parts),
        )

        log_agent_decision(
            self.name,
            f"Story {'PASSED' if overall_passed else 'FAILED'}",
            report.summary,
        )

        return report

    def quick_verify(self, changed_files: list[str] | None = None) -> bool:
        """Run a quick verification (type check and lint only).

        Args:
            changed_files: Optional list of files to focus on.

        Returns:
            True if type check passes, False otherwise.
        """
        type_result = self.run_type_check()
        return type_result.passed

    def get_failed_criteria(
        self,
        report: VerificationReport
    ) -> list[CriterionResult]:
        """Extract failed criteria from a report.

        Args:
            report: The verification report to analyze.

        Returns:
            List of CriterionResult with FAIL status.
        """
        return [
            cr for cr in report.criteria_results
            if cr.status == VerificationStatus.FAIL
        ]

    def suggest_fixes(self, report: VerificationReport) -> str:
        """Generate suggestions for fixing failed verifications.

        Uses the LLM to analyze failures and suggest fixes.

        Args:
            report: The verification report with failures.

        Returns:
            String with suggested fixes.
        """
        if report.overall_passed:
            return "All verifications passed. No fixes needed."

        failures = []
        for cr in report.criteria_results:
            if cr.status == VerificationStatus.FAIL:
                failures.append(f"- {cr.criterion}: {cr.details}")

        if report.type_check and not report.type_check.passed:
            failures.append(f"- Type check failed with {report.type_check.error_count} errors")
            for err in report.type_check.errors[:3]:
                failures.append(f"  - {err}")

        prompt = f"""Based on these verification failures, suggest fixes:

Story: {report.story_id} - {report.story_title}

Failures:
{chr(10).join(failures)}

Provide specific, actionable suggestions to fix each failure."""

        return self.chat(prompt)

    def reset(self) -> None:
        """Reset the QA Tester state."""
        self.current_story = None
        self.changed_files = []
        self.clear_history()
        log_agent_action(self.name, "State reset", "Ready for new verification")
