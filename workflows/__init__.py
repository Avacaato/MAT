"""MAT Workflows module.

Provides workflow implementations for project setup, PRD generation, and build processes.
"""

from workflows.prd_generator import PRDDocument, PRDGenerator

__all__ = [
    "PRDGenerator",
    "PRDDocument",
]
