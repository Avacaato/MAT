"""MAT Orchestrator module.

Provides the AgentOrchestrator for coordinating multiple agents.
"""

from orchestrator.coordinator import (
    AgentOrchestrator,
    AgentType,
    TaskContext,
    TaskResult,
)

__all__ = [
    "AgentOrchestrator",
    "AgentType",
    "TaskContext",
    "TaskResult",
]
