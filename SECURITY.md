# Security Policy

## Supported Versions

PolicyRail is currently maintained as a single active minor line.

| Version | Supported |
| --- | --- |
| `0.6.x` | Yes |
| `<0.6.0` | No |

## Security Scope

PolicyRail is a guardrails library for GenAI runtimes. Its goal is to reduce avoidable risk in common application paths such as:

- prompt-injection preflight checks
- trust-boundary separation between trusted and untrusted context
- tool allowlisting and human-review gating
- outbound validation for common secret and prompt leaks
- audit logging with minimized, redacted events
- MCP tool governance for `tools/list` and `tools/call`

## Security Non-Goals

PolicyRail is not a complete security boundary by itself. In particular, it does not replace:

- application authentication or authorization
- network security controls
- secrets management systems
- sandboxing or operating-system isolation
- provider-side safety systems
- domain-specific compliance reviews

Using PolicyRail does not make an unsafe agent or application safe by default if surrounding infrastructure is permissive.

## Recommended Deployment Posture

For production environments, we recommend:

1. Use a remote preflight classifier or a validated internal classifier, not only the local baseline.
2. Treat remote judge degradation as operationally significant and monitor it.
3. Replace or extend the default audit sink with your enterprise observability platform.
4. Keep sensitive tools behind explicit review or out-of-band approval.
5. Validate MCP tool schemas and keep the allowlist small.
6. Add domain-specific output validation for PII, regulated content, and internal secrets.

## Reporting a Vulnerability

If you believe you found a security issue in PolicyRail:

1. Do not open a public issue with exploit details.
2. Prefer a private security advisory on GitHub when available.
3. If private reporting is not available, contact the maintainer directly before public disclosure.
4. Include reproduction steps, affected version, impact, and any suggested mitigation.

We will prioritize vulnerabilities that affect:

- privilege escalation through tool execution
- unintended prompt or secret disclosure
- unsafe fail-open behavior during degraded classifier or transport states
- MCP transport or request-handling flaws that could lead to unsafe execution
