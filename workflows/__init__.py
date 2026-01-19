"""MAT Workflows module.

Provides workflow implementations for project setup, PRD generation, and build processes.
"""

from workflows.edge_cases import (
    EdgeCase,
    EdgeCaseAnalyzer,
    EdgeCaseReport,
)
from workflows.prd_generator import PRDDocument, PRDGenerator
from workflows.prd_to_json import (
    PRDJson,
    PRDToJsonConverter,
    StoryData,
)
from workflows.story_quality import (
    QualityIssue,
    QualityReport,
    StoryQualityChecker,
    StorySpec,
)

__all__ = [
    "PRDGenerator",
    "PRDDocument",
    "QualityIssue",
    "QualityReport",
    "StoryQualityChecker",
    "StorySpec",
    "EdgeCase",
    "EdgeCaseAnalyzer",
    "EdgeCaseReport",
    "PRDJson",
    "PRDToJsonConverter",
    "StoryData",
]
