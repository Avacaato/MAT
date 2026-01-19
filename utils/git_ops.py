"""Git operations for Ralph build loop.

Provides git operations for automatically committing and pushing progress.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)


class GitOpsError(Exception):
    """Base exception for git operations errors."""


@dataclass
class GitResult:
    """Result of a git operation."""

    success: bool
    message: str
    output: str = ""


def _get_project_dir() -> Path:
    """Get the configured project directory."""
    settings = get_settings()
    return Path(settings.project_dir).resolve()


def _run_git_command(
    args: list[str],
    cwd: Optional[Path] = None,
) -> GitResult:
    """Run a git command and return the result.

    Args:
        args: Git command arguments (e.g., ["status", "--porcelain"])
        cwd: Working directory for the command (defaults to project dir)

    Returns:
        GitResult with success status, message, and command output
    """
    if cwd is None:
        cwd = _get_project_dir()

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout for git operations
        )

        if result.returncode == 0:
            return GitResult(
                success=True,
                message="Command completed successfully",
                output=result.stdout.strip(),
            )
        else:
            return GitResult(
                success=False,
                message=result.stderr.strip() or "Command failed",
                output=result.stdout.strip(),
            )
    except subprocess.TimeoutExpired:
        return GitResult(
            success=False,
            message="Git command timed out",
        )
    except FileNotFoundError:
        return GitResult(
            success=False,
            message="Git is not installed or not in PATH",
        )
    except Exception as e:
        return GitResult(
            success=False,
            message=f"Git command error: {e}",
        )


def is_git_repo(path: Optional[Path] = None) -> bool:
    """Check if a directory is a git repository.

    Args:
        path: Directory to check (defaults to project dir)

    Returns:
        True if directory is a git repository
    """
    if path is None:
        path = _get_project_dir()

    result = _run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return result.success and result.output.lower() == "true"


def has_remote(remote_name: str = "origin", path: Optional[Path] = None) -> bool:
    """Check if a remote is configured.

    Args:
        remote_name: Name of the remote to check
        path: Working directory (defaults to project dir)

    Returns:
        True if the remote exists
    """
    if path is None:
        path = _get_project_dir()

    result = _run_git_command(["remote", "get-url", remote_name], cwd=path)
    return result.success


def git_add(files: list[str] | str, path: Optional[Path] = None) -> GitResult:
    """Stage files for commit.

    Args:
        files: File path(s) to stage. Can be a single path string or list of paths.
               Use "." or "-A" to stage all changes.
        path: Working directory (defaults to project dir)

    Returns:
        GitResult with operation status
    """
    if path is None:
        path = _get_project_dir()

    # Check if git repo
    if not is_git_repo(path):
        logger.warning(f"Not a git repository: {path}")
        return GitResult(
            success=False,
            message=f"Not a git repository: {path}",
        )

    # Normalize files to list
    if isinstance(files, str):
        files = [files]

    result = _run_git_command(["add"] + files, cwd=path)

    if result.success:
        logger.info(f"Staged files: {', '.join(files)}")
    else:
        logger.error(f"Failed to stage files: {result.message}")

    return result


def git_commit(message: str, path: Optional[Path] = None) -> GitResult:
    """Create a commit with the staged changes.

    Args:
        message: Commit message
        path: Working directory (defaults to project dir)

    Returns:
        GitResult with operation status
    """
    if path is None:
        path = _get_project_dir()

    # Check if git repo
    if not is_git_repo(path):
        logger.warning(f"Not a git repository: {path}")
        return GitResult(
            success=False,
            message=f"Not a git repository: {path}",
        )

    # Check for staged changes
    status_result = _run_git_command(["diff", "--cached", "--quiet"], cwd=path)
    if status_result.success:
        # No staged changes (exit code 0 means no diff)
        logger.warning("No staged changes to commit")
        return GitResult(
            success=False,
            message="No staged changes to commit",
        )

    result = _run_git_command(["commit", "-m", message], cwd=path)

    if result.success:
        logger.info(f"Created commit: {message}")
    else:
        logger.error(f"Failed to create commit: {result.message}")

    return result


def git_push(
    remote: str = "origin",
    branch: Optional[str] = None,
    path: Optional[Path] = None,
) -> GitResult:
    """Push commits to remote repository.

    Args:
        remote: Remote name (default: origin)
        branch: Branch to push (default: current branch)
        path: Working directory (defaults to project dir)

    Returns:
        GitResult with operation status. Logs warning but doesn't fail
        if no remote is configured.
    """
    if path is None:
        path = _get_project_dir()

    # Check if git repo
    if not is_git_repo(path):
        logger.warning(f"Not a git repository: {path}")
        return GitResult(
            success=False,
            message=f"Not a git repository: {path}",
        )

    # Check if remote exists
    if not has_remote(remote, path):
        logger.warning(f"No remote '{remote}' configured, skipping push")
        return GitResult(
            success=True,  # Don't fail, just skip
            message=f"No remote '{remote}' configured, push skipped",
        )

    # Get current branch if not specified
    if branch is None:
        branch_result = _run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=path
        )
        if branch_result.success:
            branch = branch_result.output
        else:
            logger.error(f"Failed to get current branch: {branch_result.message}")
            return GitResult(
                success=False,
                message=f"Failed to get current branch: {branch_result.message}",
            )

    # Push with upstream tracking
    result = _run_git_command(["push", "-u", remote, branch], cwd=path)

    if result.success:
        logger.info(f"Pushed to {remote}/{branch}")
    else:
        # Log error but consider this a graceful failure
        logger.error(f"Push failed: {result.message}")

    return result


def git_status(path: Optional[Path] = None) -> GitResult:
    """Get the status of the working tree.

    Args:
        path: Working directory (defaults to project dir)

    Returns:
        GitResult with status output
    """
    if path is None:
        path = _get_project_dir()

    if not is_git_repo(path):
        return GitResult(
            success=False,
            message=f"Not a git repository: {path}",
        )

    return _run_git_command(["status", "--short"], cwd=path)


def auto_commit_story(
    story_id: str,
    story_title: str,
    changed_files: Optional[list[str]] = None,
    path: Optional[Path] = None,
) -> GitResult:
    """Automatically commit changes after completing a story.

    This is a convenience function that stages all changes (or specified files)
    and commits with a formatted message.

    Args:
        story_id: The story ID (e.g., "US-017")
        story_title: The story title
        changed_files: Optional list of specific files to stage. If None, stages all.
        path: Working directory (defaults to project dir)

    Returns:
        GitResult with operation status
    """
    if path is None:
        path = _get_project_dir()

    # Check if git repo
    if not is_git_repo(path):
        logger.warning(f"Not a git repository: {path}, skipping auto-commit")
        return GitResult(
            success=False,
            message=f"Not a git repository: {path}",
        )

    # Stage files
    files_to_add = changed_files if changed_files else ["-A"]
    add_result = git_add(files_to_add, path)
    if not add_result.success:
        return add_result

    # Create commit message
    commit_message = f"feat: {story_id} - {story_title}"

    # Commit
    commit_result = git_commit(commit_message, path)
    if not commit_result.success:
        # If no changes, that's okay
        if "No staged changes" in commit_result.message:
            logger.info("No changes to commit for this story")
            return GitResult(
                success=True,
                message="No changes to commit",
            )
        return commit_result

    return commit_result


def auto_commit_and_push(
    story_id: str,
    story_title: str,
    changed_files: Optional[list[str]] = None,
    path: Optional[Path] = None,
) -> GitResult:
    """Automatically commit and push changes after completing a story.

    This is a convenience function that stages, commits, and pushes.
    Push failures are logged but don't cause the function to fail.

    Args:
        story_id: The story ID (e.g., "US-017")
        story_title: The story title
        changed_files: Optional list of specific files to stage. If None, stages all.
        path: Working directory (defaults to project dir)

    Returns:
        GitResult with operation status (push failures are warnings, not errors)
    """
    # Commit first
    commit_result = auto_commit_story(story_id, story_title, changed_files, path)
    if not commit_result.success:
        return commit_result

    # If there was nothing to commit, don't try to push
    if "No changes to commit" in commit_result.message:
        return commit_result

    # Try to push, but handle failures gracefully
    push_result = git_push(path=path)
    if not push_result.success and "push skipped" not in push_result.message.lower():
        # Push failed but commit succeeded
        logger.warning(f"Commit succeeded but push failed: {push_result.message}")
        return GitResult(
            success=True,  # Overall success since commit worked
            message=f"Commit created, push failed: {push_result.message}",
            output=commit_result.output,
        )

    return GitResult(
        success=True,
        message="Changes committed and pushed",
        output=commit_result.output,
    )
