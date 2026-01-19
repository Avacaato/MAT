"""File operations for MAT agents.

Provides sandboxed file operations limited to the configured project directory.
"""

import fnmatch
import logging
import os
from pathlib import Path
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)

# Maximum file size for reads (1MB)
MAX_FILE_SIZE = 1024 * 1024

# Common binary file extensions to skip
BINARY_EXTENSIONS = frozenset({
    ".exe", ".dll", ".so", ".dylib", ".bin", ".obj", ".o", ".a", ".lib",
    ".pyc", ".pyo", ".class", ".jar", ".war",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".wav", ".flac",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".db", ".sqlite", ".sqlite3",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
})


class FileOpsError(Exception):
    """Base exception for file operations errors."""


def _get_project_dir() -> Path:
    """Get the configured project directory."""
    settings = get_settings()
    return Path(settings.project_dir).resolve()


def _is_path_safe(path: Path, project_dir: Path) -> bool:
    """Check if a path is safe (within project directory).

    Rejects paths with '..' or absolute paths outside project directory.
    """
    try:
        resolved = path.resolve()
        # Check if resolved path is within project directory
        resolved.relative_to(project_dir)
        return True
    except ValueError:
        return False


def _is_binary_file(path: Path) -> bool:
    """Check if a file appears to be binary based on extension."""
    return path.suffix.lower() in BINARY_EXTENSIONS


def read_file(path: str | Path, project_dir: Optional[str | Path] = None) -> str:
    """Read file contents from the project directory.

    Args:
        path: File path (relative to project directory or absolute within it)
        project_dir: Optional override for project directory

    Returns:
        File contents as string, or empty string if file doesn't exist

    Raises:
        FileOpsError: If path is outside project directory or other safety violation
    """
    proj_dir = Path(project_dir).resolve() if project_dir else _get_project_dir()
    file_path = Path(path)

    # Make path absolute relative to project dir if not already absolute
    if not file_path.is_absolute():
        file_path = proj_dir / file_path

    # Security check: ensure path is within project directory
    if not _is_path_safe(file_path, proj_dir):
        raise FileOpsError(
            f"Access denied: path '{path}' is outside project directory '{proj_dir}'"
        )

    resolved_path = file_path.resolve()

    # Check if file exists
    if not resolved_path.exists():
        logger.warning(f"File not found: {resolved_path}")
        return ""

    # Check if it's a file (not directory)
    if not resolved_path.is_file():
        logger.warning(f"Path is not a file: {resolved_path}")
        return ""

    # Check for binary files
    if _is_binary_file(resolved_path):
        logger.warning(f"Skipping binary file: {resolved_path}")
        return ""

    # Check file size
    file_size = resolved_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        raise FileOpsError(
            f"File too large: {resolved_path} ({file_size} bytes > {MAX_FILE_SIZE} bytes)"
        )

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        logger.warning(f"Skipping binary file (decode error): {resolved_path}")
        return ""


def write_file(
    path: str | Path,
    content: str,
    project_dir: Optional[str | Path] = None,
) -> Path:
    """Write content to a file in the project directory.

    Creates parent directories automatically if they don't exist.

    Args:
        path: File path (relative to project directory or absolute within it)
        content: Content to write
        project_dir: Optional override for project directory

    Returns:
        The resolved path where the file was written

    Raises:
        FileOpsError: If path is outside project directory
    """
    proj_dir = Path(project_dir).resolve() if project_dir else _get_project_dir()
    file_path = Path(path)

    # Make path absolute relative to project dir if not already absolute
    if not file_path.is_absolute():
        file_path = proj_dir / file_path

    # Security check: ensure path is within project directory
    if not _is_path_safe(file_path, proj_dir):
        raise FileOpsError(
            f"Access denied: path '{path}' is outside project directory '{proj_dir}'"
        )

    resolved_path = file_path.resolve()

    # Create parent directories if needed
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with open(resolved_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Wrote file: {resolved_path}")
    return resolved_path


def list_files(
    directory: str | Path = ".",
    pattern: str = "*",
    project_dir: Optional[str | Path] = None,
) -> list[Path]:
    """List files in a directory matching a pattern.

    Args:
        directory: Directory to search (relative to project directory)
        pattern: Glob pattern to match (e.g., "*.py", "**/*.md")
        project_dir: Optional override for project directory

    Returns:
        List of matching file paths (relative to project directory)

    Raises:
        FileOpsError: If directory is outside project directory
    """
    proj_dir = Path(project_dir).resolve() if project_dir else _get_project_dir()
    search_dir = Path(directory)

    # Make path absolute relative to project dir if not already absolute
    if not search_dir.is_absolute():
        search_dir = proj_dir / search_dir

    # Security check: ensure path is within project directory
    if not _is_path_safe(search_dir, proj_dir):
        raise FileOpsError(
            f"Access denied: directory '{directory}' is outside project directory '{proj_dir}'"
        )

    resolved_dir = search_dir.resolve()

    if not resolved_dir.exists():
        logger.warning(f"Directory not found: {resolved_dir}")
        return []

    if not resolved_dir.is_dir():
        logger.warning(f"Path is not a directory: {resolved_dir}")
        return []

    # Collect matching files
    matching_files: list[Path] = []

    if "**" in pattern:
        # Recursive glob
        for file_path in resolved_dir.glob(pattern):
            if file_path.is_file():
                # Return path relative to project directory
                try:
                    relative_path = file_path.relative_to(proj_dir)
                    matching_files.append(relative_path)
                except ValueError:
                    # Skip files outside project dir (shouldn't happen)
                    pass
    else:
        # Non-recursive: walk top-level only
        for entry in resolved_dir.iterdir():
            if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                try:
                    relative_path = entry.relative_to(proj_dir)
                    matching_files.append(relative_path)
                except ValueError:
                    pass

    return sorted(matching_files)
