# PolicyRail MCP Support

PolicyRail includes a focused MCP client layer for secure tool governance. It is designed for applications that want to discover, allowlist, validate, and execute MCP tools without adopting a full agent framework.

## Positioning

PolicyRail does not attempt to implement the entire MCP surface area. Instead, it provides a pragmatic and security-oriented subset centered on:

- `initialize`
- `tools/list`
- `tools/call`
- client handling for server notifications and server requests
- roots support through `roots/list`
- transport support for stdio and Streamable HTTP

This is enough for many RAG assistants, internal copilots, and tool-governed GenAI applications.

## Supported Protocol Revisions

PolicyRail currently recognizes these MCP protocol revisions:

- `2025-11-25`
- `2025-06-18`
- `2025-03-26`
- `2024-11-05`

By default, the client negotiates strictly and raises an error if the server responds with a version outside this set.

## Transport Support Matrix

| Capability | `InMemoryMCPTransport` | `StdioMCPTransport` | `StreamableHTTPMCPTransport` |
| --- | --- | --- | --- |
| `initialize` | Yes | Yes | Yes |
| `tools/list` | Yes | Yes | Yes |
| `tools/call` | Yes | Yes | Yes |
| Server notifications during active request | Yes | Yes | Yes |
| Server requests during active request | Yes | Yes | Yes |
| `roots/list` handled by client | Yes | Yes | Yes |
| HTTP GET server stream | No | No | Yes |
| Session ID support | No | No | Yes |
| `Last-Event-Id` reuse | No | No | Yes |

## Security Behavior

PolicyRail adds guardrails on top of MCP usage:

1. Tools are not executed just because a model proposed them.
2. MCP tools are translated into `ToolSpec` entries and remain subject to the policy engine.
3. `MCPToolExecutor` validates `tool_call.arguments` against the discovered `inputSchema` before execution.
4. Invalid tool arguments are retained for review instead of being executed blindly.

## Client-Side Features

`JSONRPCMCPClient` supports:

- explicit protocol negotiation checks
- roots capability advertisement when roots are configured
- built-in handling for `ping`
- built-in handling for `roots/list`
- custom server request handlers
- custom server notification handlers
- optional HTTP GET stream listener for server-initiated notifications and requests

## Current Deliberate Limits

PolicyRail is not yet a complete general-purpose MCP SDK. In particular, it does not currently provide first-class client abstractions for:

- resources
- prompts
- sampling
- completions
- elicitation UX
- OAuth flows and resource-indicator plumbing
- progress/event presentation abstractions

Those features may be added over time, but they are intentionally out of scope for the current library-first guardrails core.
