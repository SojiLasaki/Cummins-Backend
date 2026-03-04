# core/services/system_orchestrator.py

from __future__ import annotations

from typing import Any

from apps.core.services.workflow_pipeline import FailureDetectedResult, WorkflowPipeline


class SystemOrchestrator:
    """
    Backwards-compatible facade over the workflow pipeline.
    """

    def __init__(self):
        self.pipeline = WorkflowPipeline()

    def run_full_diagnostic_pipeline(self, ticket_data: dict[str, Any], *, user: Any = None) -> FailureDetectedResult:
        return self.pipeline.failure_detected(ticket_data, user=user)