from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .client import DEFAULT_MCP_PROTOCOL_VERSION, MCPTransportSessionExpired
from .models import MCPServerStream

TransportMessageHandler = Callable[[dict[str, Any]], dict[str, Any] | None]


class StdioMCPTransport:
    def __init__(
        self,
        command: list[str] | tuple[str, ...],
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.command = list(command)
        self.cwd = str(cwd) if cwd is not None else None
        self.env = dict(env or {})
        self.timeout = timeout
        self._protocol_version = DEFAULT_MCP_PROTOCOL_VERSION
        self._next_id = 1
        self._process: subprocess.Popen[str] | None = None
        self._stderr_tail: deque[str] = deque(maxlen=20)
        self._response_buffer: dict[int, dict[str, Any]] = {}
        self._pending_responses: dict[int, queue.Queue[dict[str, Any] | None]] = {}
        self._io_lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._message_handler: TransportMessageHandler | None = None

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_process()
        is_notification = method.startswith("notifications/")

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        pending_queue: queue.Queue[dict[str, Any] | None] | None = None
        request_id: int | None = None

        with self._io_lock:
            if not is_notification:
                request_id = self._next_id
                self._next_id += 1
                payload["id"] = request_id
                if request_id in self._response_buffer:
                    return self._unwrap_response(self._response_buffer.pop(request_id))
                pending_queue = queue.Queue(maxsize=1)
                self._pending_responses[request_id] = pending_queue

            self._write_payload(payload)

        if is_notification:
            return {}

        assert request_id is not None
        assert pending_queue is not None

        try:
            message = pending_queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            self._pending_responses.pop(request_id, None)
            raise TimeoutError(
                f"Timeout ao aguardar resposta MCP via stdio para '{method}'. "
                f"Stderr recente: {self._stderr_preview()}"
            ) from exc

        if message is None:
            self._pending_responses.pop(request_id, None)
            raise RuntimeError(
                "Processo MCP via stdio encerrou antes de responder. "
                f"Stderr recente: {self._stderr_preview()}"
            )

        self._pending_responses.pop(request_id, None)
        return self._unwrap_response(message)

    def set_message_handler(self, handler: TransportMessageHandler) -> None:
        self._message_handler = handler

    def set_protocol_version(self, protocol_version: str) -> None:
        self._protocol_version = protocol_version

    def close(self) -> None:
        if self._process is None:
            return

        for pending_queue in self._pending_responses.values():
            pending_queue.put_nowait(None)
        self._pending_responses.clear()

        try:
            if self._process.stdin:
                self._process.stdin.close()
        except OSError:
            pass
        try:
            if self._process.stdout:
                self._process.stdout.close()
        except OSError:
            pass
        try:
            if self._process.stderr:
                self._process.stderr.close()
        except OSError:
            pass

        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)

        self._process = None

    def _ensure_process(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return

        env = os.environ.copy()
        env.update(self.env)
        self._stderr_tail.clear()
        self._response_buffer.clear()
        self._pending_responses.clear()

        self._process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

        assert self._process.stdout is not None
        assert self._process.stderr is not None

        self._stdout_thread = threading.Thread(
            target=self._pump_stdout,
            args=(self._process.stdout,),
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._pump_stderr,
            args=(self._process.stderr,),
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _write_payload(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Processo MCP via stdio nao esta disponivel.")

        self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _pump_stdout(self, stream) -> None:
        try:
            for line in stream:
                parsed = self._parse_message(line)
                if parsed is None:
                    continue
                for message in _iter_messages(parsed):
                    self._dispatch_message(message)
        finally:
            for pending_queue in list(self._pending_responses.values()):
                try:
                    pending_queue.put_nowait(None)
                except queue.Full:
                    pass

    def _dispatch_message(self, message: dict[str, Any]) -> None:
        message_id = message.get("id")
        if isinstance(message_id, int) and "method" not in message:
            pending_queue = self._pending_responses.get(message_id)
            if pending_queue is not None:
                pending_queue.put_nowait(message)
                return
            self._response_buffer[message_id] = message
            return

        if "method" in message and self._message_handler is not None:
            response = self._message_handler(message)
            if response is not None:
                with self._io_lock:
                    self._write_payload(response)

    def _pump_stderr(self, stream) -> None:
        for line in stream:
            compact = line.strip()
            if compact:
                self._stderr_tail.append(compact)

    @staticmethod
    def _parse_message(raw_message: str) -> dict[str, Any] | list[Any] | None:
        candidate = raw_message.strip()
        if not candidate:
            return None
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _unwrap_response(message: dict[str, Any]) -> dict[str, Any]:
        if "error" in message:
            error = message["error"]
            raise RuntimeError(f"Erro MCP via stdio: {error}")
        return _ensure_dict(message.get("result"))

    def _stderr_preview(self) -> str:
        if not self._stderr_tail:
            return "sem stderr"
        return " | ".join(self._stderr_tail)


class StreamableHTTPMCPTransport:
    def __init__(
        self,
        endpoint_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
        reconnect_delay: float = 1.0,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self._next_id = 1
        self._session_id: str | None = None
        self._protocol_version: str | None = None
        self._request_lock = threading.RLock()
        self._message_handler: TransportMessageHandler | None = None
        self._last_event_id: str | None = None
        self._server_stream: MCPServerStream | None = None

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        is_notification = method.startswith("notifications/")
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        request_id: int | None = None
        if not is_notification:
            request_id = self._next_id
            self._next_id += 1
            payload["id"] = request_id

        body, content_type, status = self._post_jsonrpc_envelope(
            payload,
            include_protocol_header=method != "initialize",
            accept_sse=True,
        )

        if is_notification or status == 202:
            return {}
        if status == 204 or not body:
            return {}

        if content_type == "application/json":
            message = json.loads(body.decode("utf-8"))
            return self._extract_result_from_json(message, request_id)

        if content_type == "text/event-stream":
            return self._extract_result_from_sse(body.decode("utf-8"), request_id)

        try:
            message = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Resposta MCP HTTP com content-type nao suportado: {content_type or 'desconhecido'}"
            ) from exc
        return self._extract_result_from_json(message, request_id)

    def set_message_handler(self, handler: TransportMessageHandler) -> None:
        self._message_handler = handler

    def set_protocol_version(self, protocol_version: str) -> None:
        self._protocol_version = protocol_version

    def start_server_stream(self, handler: TransportMessageHandler) -> MCPServerStream:
        self._message_handler = handler
        if self._server_stream is not None and self._server_stream.is_running:
            return self._server_stream

        stop_event = threading.Event()
        stream_handle = MCPServerStream(thread=None, stop_event=stop_event)  # type: ignore[arg-type]
        thread = threading.Thread(
            target=self._run_server_stream,
            args=(stream_handle,),
            daemon=True,
            name="policyrail-mcp-http-stream",
        )
        stream_handle.thread = thread
        self._server_stream = stream_handle
        thread.start()
        return stream_handle

    def close(self) -> None:
        if self._server_stream is not None:
            self._server_stream.close()
            self._server_stream = None

        if not self._session_id:
            return

        headers = self._build_headers(
            accept="application/json, text/event-stream",
            include_protocol_header=True,
        )
        request = urllib.request.Request(
            self.endpoint_url,
            headers=headers,
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout):
                pass
        except Exception:
            pass
        finally:
            self._session_id = None

    def _run_server_stream(self, stream_handle: MCPServerStream) -> None:
        while not stream_handle.stop_event.is_set():
            headers = self._build_headers(
                accept="text/event-stream",
                include_protocol_header=True,
            )
            if self._last_event_id:
                headers["Last-Event-Id"] = self._last_event_id

            request = urllib.request.Request(
                self.endpoint_url,
                headers=headers,
                method="GET",
            )

            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    self._update_session_id(response.headers)
                    content_type = (
                        (response.headers.get("Content-Type") or "")
                        .split(";")[0]
                        .strip()
                        .lower()
                    )
                    if content_type != "text/event-stream":
                        raise RuntimeError("Servidor MCP nao retornou SSE no endpoint GET.")

                    payload = response.read().decode("utf-8")
                    retry_ms = self._handle_sse_payload(payload)
                    if retry_ms is not None:
                        time.sleep(retry_ms / 1000.0)
                        continue
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and self._session_id:
                    self._session_id = None
                    stream_handle.last_error = MCPTransportSessionExpired(
                        "Sessao MCP HTTP expirou; e necessario reinicializar a conexao."
                    )
                    return
                if exc.code == 405:
                    stream_handle.last_error = RuntimeError(
                        "Servidor MCP nao suporta stream iniciado via HTTP GET."
                    )
                    return
                stream_handle.last_error = RuntimeError(f"Erro HTTP MCP {exc.code}")
            except Exception as exc:
                stream_handle.last_error = exc

            if not stream_handle.stop_event.wait(self.reconnect_delay):
                continue

    def _post_jsonrpc_envelope(
        self,
        payload: dict[str, Any],
        *,
        include_protocol_header: bool,
        accept_sse: bool,
    ) -> tuple[bytes, str, int]:
        with self._request_lock:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                self.endpoint_url,
                data=data,
                headers=self._build_headers(
                    accept="application/json, text/event-stream"
                    if accept_sse
                    else "application/json",
                    include_protocol_header=include_protocol_header,
                ),
                method="POST",
            )

            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    self._update_session_id(response.headers)
                    body = response.read()
                    content_type = (
                        (response.headers.get("Content-Type") or "")
                        .split(";")[0]
                        .strip()
                        .lower()
                    )
                    return body, content_type, response.status
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 404 and self._session_id:
                    self._session_id = None
                    raise MCPTransportSessionExpired(
                        "Sessao MCP HTTP expirou; uma nova inicializacao sera necessaria."
                    ) from exc
                raise RuntimeError(f"Erro HTTP MCP {exc.code}: {body}") from exc

    def _send_jsonrpc_response(self, payload: dict[str, Any]) -> None:
        self._post_jsonrpc_envelope(
            payload,
            include_protocol_header=True,
            accept_sse=False,
        )

    def _build_headers(
        self,
        *,
        accept: str,
        include_protocol_header: bool,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": accept,
            **self.headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        if include_protocol_header and self._protocol_version:
            headers["MCP-Protocol-Version"] = self._protocol_version
        return headers

    def _update_session_id(self, headers: Any) -> None:
        session_id = headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id

    def _handle_jsonrpc_message(
        self,
        message: dict[str, Any],
        *,
        request_id: int | None,
    ) -> dict[str, Any] | None:
        if "method" in message:
            if self._message_handler is None:
                return None
            response = self._message_handler(message)
            if response is not None:
                self._send_jsonrpc_response(response)
            return None

        if "error" in message:
            if request_id is None or message.get("id") == request_id:
                raise RuntimeError(f"Erro MCP HTTP: {message['error']}")
            return None

        if request_id is not None and message.get("id") == request_id:
            return _ensure_dict(message.get("result"))
        return None

    def _extract_result_from_json(
        self,
        message: dict[str, Any] | list[Any],
        request_id: int | None,
    ) -> dict[str, Any]:
        matched_result: dict[str, Any] | None = None
        for item in _iter_messages(message):
            result = self._handle_jsonrpc_message(item, request_id=request_id)
            if result is not None:
                matched_result = result
        if matched_result is None:
            raise RuntimeError("Resposta MCP HTTP nao contem o id esperado.")
        return matched_result

    def _extract_result_from_sse(
        self,
        payload: str,
        request_id: int | None,
    ) -> dict[str, Any]:
        matched_result: dict[str, Any] | None = None
        for event in _iter_sse_events(payload):
            if event.id:
                self._last_event_id = event.id
            if not event.data:
                continue
            message = json.loads(event.data)
            for item in _iter_messages(message):
                result = self._handle_jsonrpc_message(item, request_id=request_id)
                if result is not None:
                    matched_result = result
        if matched_result is None:
            raise RuntimeError("Nenhuma resposta MCP foi encontrada no stream SSE.")
        return matched_result

    def _handle_sse_payload(self, payload: str) -> int | None:
        retry_ms: int | None = None
        for event in _iter_sse_events(payload):
            if event.id:
                self._last_event_id = event.id
            if event.retry is not None:
                retry_ms = event.retry
            if not event.data:
                continue
            message = json.loads(event.data)
            for item in _iter_messages(message):
                self._handle_jsonrpc_message(item, request_id=None)
        return retry_ms


HTTPMCPTransport = StreamableHTTPMCPTransport


@dataclass(slots=True)
class _SSEEvent:
    event: str | None
    data: str
    id: str | None = None
    retry: int | None = None


def _iter_sse_events(payload: str) -> Iterable[_SSEEvent]:
    event_name: str | None = None
    data_lines: list[str] = []
    event_id: str | None = None
    retry: int | None = None

    for line in payload.splitlines():
        if not line:
            if data_lines or event_name or event_id or retry is not None:
                yield _SSEEvent(
                    event=event_name,
                    data="\n".join(data_lines),
                    id=event_id,
                    retry=retry,
                )
            event_name = None
            data_lines = []
            event_id = None
            retry = None
            continue

        if line.startswith(":"):
            continue

        field, _sep, value = line.partition(":")
        value = value.lstrip()
        if field == "event":
            event_name = value or None
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            event_id = value or None
        elif field == "retry":
            try:
                retry = int(value)
            except ValueError:
                retry = None

    if data_lines or event_name or event_id or retry is not None:
        yield _SSEEvent(
            event=event_name,
            data="\n".join(data_lines),
            id=event_id,
            retry=retry,
        )


def _iter_messages(message: dict[str, Any] | list[Any]) -> Iterable[dict[str, Any]]:
    if isinstance(message, dict):
        yield dict(message)
        return
    if isinstance(message, list):
        for item in message:
            if isinstance(item, dict):
                yield dict(item)


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
