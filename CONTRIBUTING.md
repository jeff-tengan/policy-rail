# Contributing to PolicyRail

Thanks for contributing.

PolicyRail is intentionally small, library-first, and security-oriented. The best contributions keep the public API clear, improve robustness, and avoid turning the project into a monolithic framework.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[all,release]"
python -m unittest discover -s tests -v
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[all,release]"
python -m unittest discover -s tests -v
```

## Contribution Guidelines

Please prefer changes that are:

- security-motivated and easy to reason about
- small in public surface area
- well covered by tests
- documented in the English docs first
- compatible with library-first adoption

## Project Principles

1. The model is not the final authority.
2. Security-relevant decisions should be explicit in code.
3. Guardrails should degrade safely, not silently fail open.
4. MCP support should be honest about what is implemented and what is not.
5. The package should remain usable without forcing application architecture.

## When You Change Behavior

Please update all of the following when applicable:

- unit tests
- `README.md`
- `docs/architecture.md`
- `docs/mcp.md` for MCP-related behavior
- `CHANGELOG.md`

## Pull Request Checklist

Before opening a PR, please confirm:

- tests pass locally
- new behavior is covered by at least one test
- public exports remain intentional
- documentation reflects the new behavior
- the change does not widen defaults unsafely

## Releases

PolicyRail follows semantic versioning:

- patch: bug fix or documentation-only refinement
- minor: new backward-compatible feature or hardening improvement
- major: breaking API or behavioral change
