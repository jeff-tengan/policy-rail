from __future__ import annotations

import json
import sys


def _write(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        message = json.loads(line)
        method = message.get("method")

        if method == "initialize":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {
                        "protocolVersion": message["params"]["protocolVersion"],
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "stdio-test-server", "version": "1.0.0"},
                    },
                }
            )
            continue

        if method == "notifications/initialized":
            continue

        if method == "tools/list":
            _write(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/test",
                    "params": {"stage": "before-response"},
                }
            )
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": 900,
                    "method": "roots/list",
                    "params": {},
                }
            )
            roots_response = json.loads(sys.stdin.readline())
            roots = roots_response.get("result", {}).get("roots", [])
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "search_policy_docs",
                                "description": f"Roots recebidas: {len(roots)}",
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
            continue

        if method == "tools/call":
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Query: {message['params']['arguments'].get('query', '')}",
                            }
                        ],
                        "metadata": {"server": "stdio-test-server"},
                    },
                }
            )
            continue

        if method == "ping":
            _write({"jsonrpc": "2.0", "id": message["id"], "result": {}})
            continue

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
