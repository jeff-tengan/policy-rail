from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from textwrap import shorten
from typing import Any
from uuid import uuid4

from ..core.models import (
    OutputValidation,
    PolicyDecision,
    RiskAssessment,
    SecureRequest,
    ToolCall,
    ToolExecutionResult,
)


class JsonAuditLogger:
    def __init__(
        self,
        log_path: str | Path = "logs/audit.jsonl",
        *,
        preview_width: int = 280,
        max_collection_items: int = 25,
        max_depth: int = 5,
    ) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.preview_width = preview_width
        self.max_collection_items = max_collection_items
        self.max_depth = max_depth
        self._sensitive_key_tokens = (
            "api_key",
            "apikey",
            "authorization",
            "auth",
            "bearer",
            "cookie",
            "credential",
            "password",
            "secret",
            "session",
            "token",
        )
        self._redaction_patterns = [
            re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(r"\bBearer\s+[A-Za-z0-9._=-]+\b", re.IGNORECASE),
        ]

    def record_interaction(
        self,
        *,
        request: SecureRequest,
        risk: RiskAssessment,
        decision: PolicyDecision,
        output_validation: OutputValidation,
        response_text: str,
        tool_call: ToolCall | None,
        tool_result: ToolExecutionResult | None = None,
    ) -> str:
        event_id = str(uuid4())
        payload = {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": self._sanitize_mapping(request.metadata),
            "user_input_preview": self._sanitize(request.user_input),
            "trusted_context_count": len(request.trusted_context),
            "untrusted_context_count": len(request.untrusted_context),
            "risk_score": risk.score,
            "risk_blocked": risk.blocked,
            "risk_findings": [
                {
                    "rule_id": finding.rule_id,
                    "category": finding.category,
                    "matched_text": self._sanitize(finding.matched_text),
                    "source": finding.source,
                }
                for finding in risk.findings
            ],
            "decision": decision.status,
            "decision_reasons": decision.reasons,
            "tool_name": tool_call.name if tool_call else None,
            "tool_allowed": decision.allow_tool_execution,
            "tool_execution_success": tool_result.success if tool_result else None,
            "tool_execution_metadata": (
                self._sanitize_mapping(tool_result.metadata) if tool_result else {}
            ),
            "tool_output_preview": self._preview_value(tool_result.output) if tool_result else None,
            "output_passed": output_validation.passed,
            "output_violations": output_validation.violations,
            "response_preview": self._sanitize(response_text),
        }

        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

        return event_id

    def _sanitize(self, text: str, *, width: int | None = None) -> str:
        sanitized = text
        for pattern in self._redaction_patterns:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        compact = " ".join(sanitized.split())
        return shorten(compact, width=width or self.preview_width, placeholder="...")

    def _preview_value(self, value: Any) -> str:
        return self._sanitize(repr(self._sanitize_value(value)))

    def _sanitize_mapping(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {
            str(key): self._sanitize_value(item, key_hint=str(key))
            for key, item in list(value.items())[: self.max_collection_items]
        }

    def _sanitize_value(
        self,
        value: Any,
        *,
        key_hint: str | None = None,
        depth: int = 0,
    ) -> Any:
        if self._is_sensitive_key(key_hint):
            return "[REDACTED:SENSITIVE_FIELD]"

        if depth >= self.max_depth:
            return "[TRUNCATED:MAX_DEPTH]"

        if value is None or isinstance(value, bool | int | float):
            return value

        if isinstance(value, str):
            return self._sanitize(value)

        if isinstance(value, dict):
            return {
                str(key): self._sanitize_value(
                    item,
                    key_hint=str(key),
                    depth=depth + 1,
                )
                for key, item in list(value.items())[: self.max_collection_items]
            }

        if isinstance(value, (list, tuple, set)):
            return [
                self._sanitize_value(item, depth=depth + 1)
                for item in list(value)[: self.max_collection_items]
            ]

        if isinstance(value, Path):
            return self._sanitize(str(value))

        return self._sanitize(repr(value))

    def _is_sensitive_key(self, key_hint: str | None) -> bool:
        if not key_hint:
            return False
        normalized = re.sub(r"[^a-z0-9]+", "_", key_hint.casefold())
        return any(token in normalized for token in self._sensitive_key_tokens)
