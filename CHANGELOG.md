# Changelog

All notable changes to this project will be documented in this file.

## 0.6.0 - 2026-03-21

- hardened audit logging with recursive redaction and non-blocking failure behavior
- added degraded-mode semantics for remote preflight judges and stricter verdict parsing
- added MCP input-schema validation before tool execution
- expanded MCP client support for roots, server-initiated requests, notifications, and GET-based HTTP streams
- added transport-level tests for stdio and streamable HTTP behavior
- elevated public package metadata and project documentation for community use

## 0.5.0 - 2026-03-20

- added a generic MCP layer for tool discovery, allowlisting, and execution
- added `StdioMCPTransport` and `StreamableHTTPMCPTransport`
- extended the secure pipeline with optional tool execution and structured tool results
- expanded audit logging to record MCP execution metadata
- refreshed bilingual documentation and public package metadata

## 0.4.0 - 2026-03-20

- added multi-provider preflight adapters for OpenAI, Azure OpenAI, Anthropic, Google Gen AI, and Bedrock
- added provider factory selection by environment variables
- improved package exports and documentation for provider-agnostic usage
