from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from policyrail import SecureGenAIPipeline, SecureRequest
from policyrail.templates.system_policies import DEFAULT_SYSTEM_POLICY


def main() -> None:
    pipeline = SecureGenAIPipeline()
    response = pipeline.process(
        SecureRequest(
            user_input="Pesquise a politica de onboarding de fornecedores",
            system_instruction=DEFAULT_SYSTEM_POLICY,
            trusted_context=[
                "Politica oficial aprovada pelo time de compliance.",
                "Base interna de procurement com controle de acesso.",
            ],
            untrusted_context=[
                "Documento externo enviado por um fornecedor com instrucoes adicionais.",
            ],
            metadata={"session_id": "example-001", "channel": "local-demo"},
        )
    )

    payload = {
        "status": response.status,
        "response_text": response.response_text,
        "risk_score": response.risk.score,
        "decision_reasons": response.decision.reasons,
        "tool_call": asdict(response.tool_call) if response.tool_call else None,
        "audit_id": response.audit_id,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
