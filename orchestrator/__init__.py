"""MAT Orchestrator module.

Provides the AgentOrchestrator for coordinating multiple agents
and ScaleAdapter for complexity-aware planning.
"""

from orchestrator.coordinator import (
    AgentOrchestrator,
    AgentType,
    TaskContext,
    TaskResult,
)
from orchestrator.scale_adapter import (
    ComplexityLevel,
    ScaleAdapter,
    ScaleAssessment,
)

__all__ = [
    "AgentOrchestrator",
    "AgentType",
    "ComplexityLevel",
    "ScaleAdapter",
    "ScaleAssessment",
    "TaskContext",
    "TaskResult",
]
