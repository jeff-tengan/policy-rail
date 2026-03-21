from __future__ import annotations

import json
import socket
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from policyrail import (
    JSONRPCMCPClient,
    MCPProtocolNegotiationError,
    MCPRoot,
    StdioMCPTransport,
    StreamableHTTPMCPTransport,
)

HELPERS = ROOT / "tests" / "helpers"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _HTTPMCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    roots_responses: list[dict] = []
    notification_count = 0

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(content_length).decode("utf-8"))

        if payload.get("method") == "initialize":
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "protocolVersion": payload["params"]["protocolVersion"],
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "http-test-server", "version": "1.0.0"},
                    },
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", "session-test")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if payload.get("method") == "notifications/initialized":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if payload.get("method") == "tools/list":
            body = (
                "event: message\n"
                "data: "
                + json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/test",
                        "params": {"source": "http-post-sse"},
                    }
                )
                + "\n\n"
                "event: message\n"
                "data: "
                + json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 501,
                        "method": "roots/list",
                        "params": {},
                    }
                )
                + "\n\n"
                "event: message\n"
                "id: evt-1\n"
                "data: "
                + json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": payload["id"],
                        "result": {
                            "tools": [
                                {
                                    "name": "search_policy_docs",
                                    "description": "Search docs over HTTP",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {"query": {"type": "string"}},
                                        "required": ["query"],
                                        "additionalProperties": False,
                                    },
                                }
                            ]
                        },
                    }
                )
                + "\n\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Mcp-Session-Id", "session-test")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if payload.get("id") == 501 and "result" in payload:
            self.__class__.roots_responses.append(payload)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self.__class__.notification_count += 1
        body = (
            "event: message\n"
            "id: stream-1\n"
            "data: "
            + json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/test",
                    "params": {"source": "http-get-stream"},
                }
            )
            + "\n\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", "session-test")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_DELETE(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class _UnsupportedVersionTransport:
    def request(self, method: str, params: dict | None = None) -> dict:
        if method == "initialize":
            return {
                "protocolVersion": "2099-01-01",
                "capabilities": {},
                "serverInfo": {"name": "future", "version": "1.0.0"},
            }
        return {}


class MCPTransportTests(unittest.TestCase):
    def test_stdio_transport_handles_server_requests_and_notifications(self) -> None:
        notification_payloads: list[dict] = []
        transport = StdioMCPTransport(
            command=[sys.executable, str(HELPERS / "stdio_mcp_server.py")],
            cwd=ROOT,
        )
        client = JSONRPCMCPClient(
            transport,
            roots=[MCPRoot(uri="file:///workspace", name="workspace")],
            notification_handlers={
                "notifications/test": lambda params: notification_payloads.append(dict(params or {}))
            },
        )
        try:
            tools = client.list_tools()
        finally:
            client.close()

        self.assertEqual(tools[0].name, "search_policy_docs")
        self.assertIn("Roots recebidas: 1", tools[0].description)
        self.assertEqual(notification_payloads[0]["stage"], "before-response")

    def test_http_transport_handles_sse_requests_and_get_stream(self) -> None:
        _HTTPMCPHandler.roots_responses = []
        _HTTPMCPHandler.notification_count = 0
        port = _free_port()
        server = ThreadingHTTPServer(("127.0.0.1", port), _HTTPMCPHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        notification_payloads: list[dict] = []
        signal = threading.Event()

        def _on_notification(params: dict | None) -> None:
            notification_payloads.append(dict(params or {}))
            signal.set()

        transport = StreamableHTTPMCPTransport(f"http://127.0.0.1:{port}/mcp", timeout=2.0)
        client = JSONRPCMCPClient(
            transport,
            roots=[MCPRoot(uri="file:///workspace", name="workspace")],
            notification_handlers={"notifications/test": _on_notification},
        )

        try:
            tools = client.list_tools()
            stream = client.start_server_stream()
            self.assertTrue(signal.wait(timeout=3.0))
            stream.close()
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2.0)

        self.assertEqual(tools[0].name, "search_policy_docs")
        self.assertTrue(any(item.get("source") == "http-post-sse" for item in notification_payloads))
        self.assertTrue(any(item.get("source") == "http-get-stream" for item in notification_payloads))
        self.assertEqual(
            _HTTPMCPHandler.roots_responses[0]["result"]["roots"][0]["uri"],
            "file:///workspace",
        )

    def test_client_rejects_unsupported_protocol_version_when_strict(self) -> None:
        client = JSONRPCMCPClient(_UnsupportedVersionTransport())
        with self.assertRaises(MCPProtocolNegotiationError):
            client.initialize()


if __name__ == "__main__":
    unittest.main()
