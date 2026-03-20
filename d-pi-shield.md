# D-PI Shield

Portuguese translation: [d-pi-shield.pt-BR.md](./d-pi-shield.pt-BR.md)

D-PI Shield is the defense-in-depth lens behind PolicyRail. It is not a second framework inside the repository. It is the conceptual model that explains why the library separates detection, trust boundaries, tool policy, validation, and observability instead of treating prompt injection as a single regex problem.

## Overview

The goal of D-PI Shield is to help LLM applications start with a safer default posture:

- detect attack signals early
- partition context by trust level
- keep authority outside the model
- validate tools before execution
- validate outbound content before release
- observe everything through audit trails

## Defense Pipeline

```text
Detect -> Partition -> Isolate -> Generate -> Validate -> Enforce -> Observe
```

## Principles

- The LLM is probabilistic and should not decide sensitive actions alone.
- External context may enrich an answer, but it must not become trusted instruction.
- Tools should operate through allowlists and, when sensitive, human approval.
- Model outputs need a final validation pass before they leave the system.

## Baseline Attack Families

The current baseline is designed to surface signals associated with:

- prompt override attempts
- role escalation
- guardrail bypass attempts
- tool injection
- secret or system-prompt exfiltration
- encoding and obfuscation patterns

## Mapping to the Repository

- `src/policyrail/core/classifiers.py`: structured preflight classification contracts
- `src/policyrail/core/detectors.py`: prompt-injection risk scoring
- `src/policyrail/core/partitioning.py`: trusted vs untrusted prompt envelope
- `src/policyrail/core/policies.py`: execution policy and tool governance
- `src/policyrail/core/validators.py`: outbound validation
- `src/policyrail/pipeline/secure_pipeline.py`: orchestration of the secure flow
- `src/policyrail/observability/audit.py`: audit persistence

## How to Use This Note

Treat this document as a conceptual entry point. The executable implementation lives in the Python package, but this note is useful when:

- explaining the security model to product or platform teams
- aligning requirements before writing provider adapters
- reviewing whether a new feature belongs in detection, policy, validation, or observability
