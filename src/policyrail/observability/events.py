from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4


@dataclass(slots=True)
class AuditEvent:
    """Structured representation of a single audit event.

    This decouples event data from the persistence mechanism so that
    multiple emitters (JSONL file, SIEM, OpenTelemetry, webhooks) can
    consume the same event without coupling to ``JsonAuditLogger``.
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    user_input_preview: str = ""
    trusted_context_count: int = 0
    untrusted_context_count: int = 0
    risk_score: int = 0
    risk_blocked: bool = False
    risk_findings: list[dict[str, Any]] = field(default_factory=list)
    decision: str = ""
    decision_reasons: list[str] = field(default_factory=list)
    tool_name: str | None = None
    tool_allowed: bool = False
    tool_execution_success: bool | None = None
    tool_execution_metadata: dict[str, Any] = field(default_factory=dict)
    tool_output_preview: str | None = None
    output_passed: bool = True
    output_violations: list[str] = field(default_factory=list)
    response_preview: str = ""
    sanitization_applied: bool = False
    sanitization_rules: list[str] = field(default_factory=list)


@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for pluggable audit-event sinks.

    Implement this protocol to forward audit events to external systems
    (SIEM, OpenTelemetry, event buses, webhooks) without replacing or
    modifying ``JsonAuditLogger``.

    Example::

        class SIEMEmitter:
            def emit(self, event: AuditEvent) -> None:
                siem_client.send(asdict(event))

        pipeline = SecureGenAIPipeline(
            event_emitters=[SIEMEmitter()],
        )
    """

    def emit(self, event: AuditEvent) -> None: ...


class InMemoryEventEmitter:
    """Simple in-memory emitter for testing and debugging."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        self.events.append(event)
