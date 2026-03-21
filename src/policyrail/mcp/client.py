from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from .._version import __version__
from .models import MCPRoot, MCPServerStream, MCPTool, MCPToolResult

DEFAULT_MCP_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_MCP_PROTOCOL_VERSIONS = (
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)

JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_INVALID_REQUEST_CONTEXT = -32000

ServerRequestHandler = Callable[[dict[str, Any] | None], dict[str, Any] | None]
ServerNotificationHandler = Callable[[dict[str, Any] | None], None]
TransportMessageHandler = Callable[[dict[str, Any]], dict[str, Any] | None]


class MCPTransportSessionExpired(RuntimeError):
    pass


class MCPProtocolNegotiationError(RuntimeError):
    pass


class MCPTransport(Protocol):
    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


class MCPClient(Protocol):
    def list_tools(self) -> list[MCPTool]:
        ...

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        ...


class JSONRPCMCPClient:
    def __init__(
        self,
        transport: MCPTransport,
        *,
        client_name: str = "policyrail",
        client_version: str = __version__,
        protocol_version: str = DEFAULT_MCP_PROTOCOL_VERSION,
        capabilities: dict[str, Any] | None = None,
        roots: Iterable[MCPRoot | dict[str, Any] | str | Path] | None = None,
        roots_provider: Callable[[], Iterable[MCPRoot | dict[str, Any] | str | Path]] | None = None,
        request_handlers: dict[str, ServerRequestHandler] | None = None,
        notification_handlers: dict[str, ServerNotificationHandler] | None = None,
        supported_protocol_versions: tuple[str, ...] = SUPPORTED_MCP_PROTOCOL_VERSIONS,
        strict_protocol_negotiation: bool = True,
        auto_initialize: bool = True,
    ) -> None:
        self.transport = transport
        self.client_name = client_name
        self.client_version = client_version
        self.protocol_version = protocol_version
        self.supported_protocol_versions = tuple(supported_protocol_versions)
        self.strict_protocol_negotiation = strict_protocol_negotiation
        self.capabilities = self._build_capabilities(capabilities, roots, roots_provider)
        self._roots = list(roots or [])
        self._roots_provider = roots_provider
        self.auto_initialize = auto_initialize
        self._initialized = False
        self._active_request_depth = 0
        self.negotiated_protocol_version: str | None = None
        self.server_capabilities: dict[str, Any] = {}
        self.server_info: dict[str, Any] = {}
        self.server_instructions: str | None = None
        self._request_handlers: dict[str, ServerRequestHandler] = {}
        self._notification_handlers: dict[str, ServerNotificationHandler] = {}
        self._register_builtin_handlers()
        self._request_handlers.update(dict(request_handlers or {}))
        self._notification_handlers.update(dict(notification_handlers or {}))

        if hasattr(self.transport, "set_message_handler"):
            self.transport.set_message_handler(self._handle_server_message)

    def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {
                "protocolVersion": self.negotiated_protocol_version,
                "capabilities": dict(self.server_capabilities),
                "serverInfo": dict(self.server_info),
                "instructions": self.server_instructions,
            }

        result = self._request_with_retry(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": dict(self.capabilities),
                "clientInfo": {
                    "name": self.client_name,
                    "version": self.client_version,
                },
            },
        )
        negotiated_protocol_version = str(result.get("protocolVersion", self.protocol_version))
        if (
            self.strict_protocol_negotiation
            and negotiated_protocol_version not in self.supported_protocol_versions
        ):
            raise MCPProtocolNegotiationError(
                f"Servidor MCP negociou versao nao suportada: {negotiated_protocol_version}"
            )

        self.negotiated_protocol_version = negotiated_protocol_version
        self.server_capabilities = _ensure_dict(result.get("capabilities"))
        self.server_info = _ensure_dict(result.get("serverInfo"))
        instructions = result.get("instructions")
        self.server_instructions = str(instructions) if isinstance(instructions, str) else None

        if hasattr(self.transport, "set_protocol_version"):
            self.transport.set_protocol_version(self.negotiated_protocol_version)

        self.transport.request("notifications/initialized", {})
        self._initialized = True
        return result

    def list_tools(self) -> list[MCPTool]:
        self._ensure_initialized()
        tools: list[MCPTool] = []
        cursor: str | None = None

        while True:
            params = {"cursor": cursor} if cursor else {}
            payload = self._request_with_retry("tools/list", params)
            tools.extend(self._coerce_tool(item) for item in payload.get("tools", []))
            next_cursor = payload.get("nextCursor")
            if not next_cursor:
                break
            cursor = str(next_cursor)

        return tools

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        self._ensure_initialized()
        payload = self._request_with_retry(
            "tools/call",
            {"name": name, "arguments": dict(arguments or {})},
        )
        return self._coerce_result(payload)

    def ping(self) -> dict[str, Any]:
        self._ensure_initialized()
        return self._request_with_retry("ping", {})

    def register_request_handler(self, method: str, handler: ServerRequestHandler) -> None:
        self._request_handlers[method] = handler

    def register_notification_handler(
        self,
        method: str,
        handler: ServerNotificationHandler,
    ) -> None:
        self._notification_handlers[method] = handler

    def start_server_stream(self) -> MCPServerStream:
        self._ensure_initialized()
        starter = getattr(self.transport, "start_server_stream", None)
        if not callable(starter):
            raise RuntimeError("O transporte MCP configurado nao suporta stream iniciado pelo servidor.")
        return starter(self._handle_server_message)

    def close(self) -> None:
        if hasattr(self.transport, "close"):
            self.transport.close()
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self.auto_initialize and not self._initialized:
            self.initialize()

    def _request_with_retry(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        self._active_request_depth += 1
        try:
            try:
                return self.transport.request(method, params)
            except MCPTransportSessionExpired:
                self._initialized = False
                self.initialize()
                return self.transport.request(method, params)
        finally:
            self._active_request_depth = max(0, self._active_request_depth - 1)

    def _handle_server_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        if not isinstance(method, str):
            return None

        if "id" in message:
            return self._handle_server_request(message)

        self._handle_server_notification(method, message.get("params"))
        return None

    def _handle_server_request(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("id")
        method = str(message.get("method"))
        params = message.get("params")

        if self._active_request_depth <= 0 and method not in {"ping"}:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": JSONRPC_INVALID_REQUEST_CONTEXT,
                    "message": (
                        "O servidor MCP enviou uma requisicao fora do contexto de uma "
                        "requisicao ativa do cliente."
                    ),
                },
            }

        handler = self._request_handlers.get(method)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": JSONRPC_METHOD_NOT_FOUND,
                    "message": f"Metodo MCP do servidor nao suportado pelo cliente: {method}",
                },
            }

        try:
            result = handler(_ensure_dict(params) if params is not None else None) or {}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": JSONRPC_INTERNAL_ERROR,
                    "message": (
                        f"Falha ao processar a requisicao MCP '{method}' no cliente "
                        f"({exc.__class__.__name__})."
                    ),
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": _ensure_dict(result),
        }

    def _handle_server_notification(
        self,
        method: str,
        params: dict[str, Any] | None,
    ) -> None:
        handler = self._notification_handlers.get(method) or self._notification_handlers.get("*")
        if handler is None:
            return
        handler(_ensure_dict(params) if params is not None else None)

    def _register_builtin_handlers(self) -> None:
        self._request_handlers["ping"] = lambda _params: {}
        self._request_handlers["roots/list"] = self._handle_roots_list_request

    def _handle_roots_list_request(self, _params: dict[str, Any] | None) -> dict[str, Any]:
        roots_payload = [root.as_payload() for root in self._resolve_roots()]
        return {"roots": roots_payload}

    def _resolve_roots(self) -> list[MCPRoot]:
        raw_roots = (
            list(self._roots_provider())
            if self._roots_provider is not None
            else list(self._roots)
        )
        return [self._normalize_root(item) for item in raw_roots]

    @staticmethod
    def _build_capabilities(
        capabilities: dict[str, Any] | None,
        roots: Iterable[MCPRoot | dict[str, Any] | str | Path] | None,
        roots_provider: Callable[[], Iterable[MCPRoot | dict[str, Any] | str | Path]] | None,
    ) -> dict[str, Any]:
        merged = dict(capabilities or {})
        if roots is not None or roots_provider is not None:
            merged.setdefault("roots", {"listChanged": False})
        return merged

    @staticmethod
    def _normalize_root(raw_root: MCPRoot | dict[str, Any] | str | Path) -> MCPRoot:
        if isinstance(raw_root, MCPRoot):
            return raw_root
        if isinstance(raw_root, (str, Path)):
            return MCPRoot(uri=str(raw_root))
        if isinstance(raw_root, dict):
            uri = str(raw_root.get("uri", "")).strip()
            name = raw_root.get("name")
            metadata = _ensure_dict(raw_root.get("_meta", raw_root.get("metadata")))
            return MCPRoot(uri=uri, name=str(name) if name else None, metadata=metadata)
        raise TypeError("Raiz MCP invalida.")

    @staticmethod
    def _coerce_tool(raw: dict[str, Any]) -> MCPTool:
        return MCPTool(
            name=str(raw["name"]),
            description=str(raw.get("description", "")),
            input_schema=_ensure_dict(raw.get("inputSchema")),
            annotations=_ensure_dict(raw.get("annotations")),
            metadata=_ensure_dict(raw.get("metadata")),
        )

    @staticmethod
    def _coerce_result(raw: dict[str, Any]) -> MCPToolResult:
        content = raw.get("content", [])
        normalized_content: list[dict[str, Any]] = []
        for item in content:
            if isinstance(item, dict):
                normalized_content.append(dict(item))
            elif item is not None:
                normalized_content.append({"type": "text", "text": str(item)})

        return MCPToolResult(
            content=normalized_content,
            structured_content=raw.get("structuredContent"),
            is_error=bool(raw.get("isError", False)),
            metadata=_ensure_dict(raw.get("metadata")),
        )


class InMemoryMCPTransport:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[MCPTool, Callable[[dict[str, Any]], Any]]] = {}
        self._protocol_version = DEFAULT_MCP_PROTOCOL_VERSION
        self._initialized = False
        self._message_handler: TransportMessageHandler | None = None

    def register_tool(
        self,
        *,
        name: str,
        description: str,
        handler: Callable[[dict[str, Any]], Any],
        input_schema: dict[str, Any] | None = None,
        annotations: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        tool = MCPTool(
            name=name,
            description=description,
            input_schema=dict(input_schema or {}),
            annotations=dict(annotations or {}),
            metadata=dict(metadata or {}),
        )
        self._tools[name] = (tool, handler)

    def set_message_handler(self, handler: TransportMessageHandler) -> None:
        self._message_handler = handler

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if method == "initialize":
            payload = dict(params or {})
            self._protocol_version = str(payload.get("protocolVersion", DEFAULT_MCP_PROTOCOL_VERSION))
            return {
                "protocolVersion": self._protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "in-memory-mcp", "version": "1.0.0"},
                "instructions": "Test transport for local MCP integration.",
            }

        if method == "notifications/initialized":
            self._initialized = True
            return {}

        if method == "tools/list":
            if not self._initialized:
                raise RuntimeError("Transporte MCP em memoria ainda nao foi inicializado.")
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                        "annotations": tool.annotations,
                        "metadata": tool.metadata,
                    }
                    for tool, _handler in self._tools.values()
                ]
            }

        if method == "tools/call":
            if not self._initialized:
                raise RuntimeError("Transporte MCP em memoria ainda nao foi inicializado.")

            payload = dict(params or {})
            name = str(payload.get("name", "")).strip()
            if name not in self._tools:
                raise KeyError(f"Tool MCP nao encontrada: {name}")

            _tool, handler = self._tools[name]
            raw_result = handler(dict(payload.get("arguments") or {}))
            result = _coerce_in_memory_result(raw_result)
            return {
                "content": result.content,
                "structuredContent": result.structured_content,
                "isError": result.is_error,
                "metadata": result.metadata,
            }

        raise ValueError(f"Metodo MCP nao suportado: {method}")

    def emit_server_request(
        self,
        *,
        request_id: int,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if self._message_handler is None:
            return None
        return self._message_handler(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": dict(params or {}),
            }
        )

    def emit_server_notification(
        self,
        *,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        if self._message_handler is None:
            return
        self._message_handler(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": dict(params or {}),
            }
        )

    def set_protocol_version(self, protocol_version: str) -> None:
        self._protocol_version = protocol_version


def _coerce_in_memory_result(value: Any) -> MCPToolResult:
    if isinstance(value, MCPToolResult):
        return value

    if isinstance(value, str):
        return MCPToolResult(content=[{"type": "text", "text": value}])

    if isinstance(value, list):
        content: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                content.append(dict(item))
            else:
                content.append({"type": "text", "text": str(item)})
        return MCPToolResult(content=content)

    if isinstance(value, dict):
        looks_like_result = any(
            key in value
            for key in ("content", "structuredContent", "structured_content", "isError", "is_error")
        )
        if looks_like_result:
            raw_content = value.get("content", [])
            content: list[dict[str, Any]] = []
            for item in raw_content:
                if isinstance(item, dict):
                    content.append(dict(item))
                else:
                    content.append({"type": "text", "text": str(item)})
            return MCPToolResult(
                content=content,
                structured_content=value.get("structuredContent", value.get("structured_content")),
                is_error=bool(value.get("isError", value.get("is_error", False))),
                metadata=_ensure_dict(value.get("metadata")),
            )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
            structured_content=value,
        )

    return MCPToolResult(content=[{"type": "text", "text": str(value)}])


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
