from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .core.detectors import PromptInjectionDetector
from .core.models import SecureRequest
from .pipeline.secure_pipeline import SecureGenAIPipeline
from .templates.system_policies import DEFAULT_SYSTEM_POLICY, default_tool_specs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="policyrail",
        description="Policy-driven guardrails para pipelines e aplicativos GenAI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    assess = subparsers.add_parser("assess", help="Avalia risco de um texto.")
    assess.add_argument("--text", required=True, help="Texto a ser avaliado.")
    assess.add_argument(
        "--source",
        default="user_input",
        help="Origem do texto para fins de auditoria.",
    )

    demo = subparsers.add_parser("demo", help="Executa a pipeline segura com adapter mock.")
    demo.add_argument("--input", required=True, help="Solicitacao principal do usuario.")
    demo.add_argument(
        "--trusted-context",
        action="append",
        default=[],
        help="Contexto confiavel. Pode ser usado varias vezes.",
    )
    demo.add_argument(
        "--untrusted-context",
        action="append",
        default=[],
        help="Contexto nao confiavel. Pode ser usado varias vezes.",
    )
    demo.add_argument(
        "--system-policy",
        default=DEFAULT_SYSTEM_POLICY,
        help="Policy de sistema a ser usada na composicao do prompt.",
    )

    subparsers.add_parser("list-tools", help="Lista a allowlist default de tools.")
    return parser


def _run_assess(text: str, source: str) -> int:
    detector = PromptInjectionDetector()
    assessment = detector.detect(text, source=source)
    print(json.dumps(asdict(assessment), indent=2, ensure_ascii=False))
    return 0


def _run_demo(
    user_input: str,
    trusted_context: list[str],
    untrusted_context: list[str],
    system_policy: str,
) -> int:
    pipeline = SecureGenAIPipeline()
    response = pipeline.process(
        SecureRequest(
            user_input=user_input,
            system_instruction=system_policy,
            trusted_context=trusted_context,
            untrusted_context=untrusted_context,
            metadata={"entrypoint": "cli-demo"},
        )
    )
    payload = {
        "status": response.status,
        "response_text": response.response_text,
        "risk_score": response.risk.score,
        "risk_findings": [finding.description for finding in response.risk.findings],
        "decision_reasons": response.decision.reasons,
        "tool_call": asdict(response.tool_call) if response.tool_call else None,
        "output_violations": response.output_validation.violations,
        "audit_id": response.audit_id,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _run_list_tools() -> int:
    tool_specs = [
        {
            "name": tool.name,
            "description": tool.description,
            "sensitive": tool.sensitive,
            "requires_human_approval": tool.requires_human_approval,
            "max_risk_score": tool.max_risk_score,
        }
        for tool in default_tool_specs()
    ]
    print(json.dumps(tool_specs, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "assess":
        return _run_assess(args.text, args.source)
    if args.command == "demo":
        return _run_demo(
            user_input=args.input,
            trusted_context=args.trusted_context,
            untrusted_context=args.untrusted_context,
            system_policy=args.system_policy,
        )
    if args.command == "list-tools":
        return _run_list_tools()
    parser.error(f"Comando nao suportado: {args.command}")
    return 2
