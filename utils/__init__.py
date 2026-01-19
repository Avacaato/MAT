"""Utility modules for MAT."""

from utils.file_ops import (
    FileOpsError,
    list_files,
    read_file,
    write_file,
)
from utils.git_ops import (
    GitOpsError,
    GitResult,
    auto_commit_and_push,
    auto_commit_story,
    git_add,
    git_commit,
    git_push,
    git_status,
    has_remote,
    is_git_repo,
)
from utils.logger import (
    StoryProgress,
    create_progress_tracker,
    get_console,
    get_logger,
    log_agent_action,
    log_agent_decision,
    log_build_complete,
    log_build_start,
    log_verbose,
    setup_logging,
)

__all__ = [
    # File operations
    "FileOpsError",
    "list_files",
    "read_file",
    "write_file",
    # Git operations
    "GitOpsError",
    "GitResult",
    "auto_commit_and_push",
    "auto_commit_story",
    "git_add",
    "git_commit",
    "git_push",
    "git_status",
    "has_remote",
    "is_git_repo",
    # Logging
    "StoryProgress",
    "create_progress_tracker",
    "get_console",
    "get_logger",
    "log_agent_action",
    "log_agent_decision",
    "log_build_complete",
    "log_build_start",
    "log_verbose",
    "setup_logging",
]
