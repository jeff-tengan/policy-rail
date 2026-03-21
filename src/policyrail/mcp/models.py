from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Any


@dataclass(slots=True)
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPToolResult:
    content: list[dict[str, Any]] = field(default_factory=list)
    structured_content: Any = None
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def text_content(self) -> str:
        chunks: list[str] = []
        for item in self.content:
            if item.get("type") == "text":
                text = item.get("text")
                if text:
                    chunks.append(str(text))
        return "\n".join(chunks).strip()


@dataclass(slots=True)
class MCPToolPolicy:
    sensitive: bool = True
    requires_human_approval: bool = True
    max_risk_score: int = 0
    description: str | None = None


@dataclass(slots=True)
class MCPRoot:
    uri: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        payload = {"uri": self.uri}
        if self.name:
            payload["name"] = self.name
        if self.metadata:
            payload["_meta"] = dict(self.metadata)
        return payload


@dataclass(slots=True)
class MCPServerStream:
    thread: Thread
    stop_event: Event
    last_error: Exception | None = None

    @property
    def is_running(self) -> bool:
        return self.thread.is_alive() and not self.stop_event.is_set()

    def close(self, *, timeout: float = 2.0) -> None:
        self.stop_event.set()
        self.thread.join(timeout=timeout)
