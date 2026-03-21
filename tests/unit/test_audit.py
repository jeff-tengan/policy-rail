from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from policyrail.core.models import OutputValidation, PolicyDecision, RiskAssessment, SecureRequest
from policyrail.observability.audit import JsonAuditLogger


class JsonAuditLoggerTests(unittest.TestCase):
    def test_logger_redacts_sensitive_metadata_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            logger = JsonAuditLogger(log_path)
            logger.record_interaction(
                request=SecureRequest(
                    user_input="Explique a politica de senhas",
                    system_instruction="policy",
                    metadata={
                        "auth_header": "Bearer super-secret-token",
                        "nested": {
                            "api_key": "sk-ABCDEFGHIJKLMNOPQRSTUV123456",
                            "safe_label": "docs",
                        },
                    },
                ),
                risk=RiskAssessment(score=0, blocked=False),
                decision=PolicyDecision(status="allow", reasons=["ok"]),
                output_validation=OutputValidation(passed=True),
                response_text="Resposta segura",
                tool_call=None,
                tool_result=None,
            )

            payload = json.loads(log_path.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["metadata"]["auth_header"], "[REDACTED:SENSITIVE_FIELD]")
        self.assertEqual(payload["metadata"]["nested"]["api_key"], "[REDACTED:SENSITIVE_FIELD]")
        self.assertEqual(payload["metadata"]["nested"]["safe_label"], "docs")
        self.assertNotIn("super-secret-token", json.dumps(payload, ensure_ascii=False))

    def test_logger_serializes_non_json_safe_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            logger = JsonAuditLogger(log_path)
            event_id = logger.record_interaction(
                request=SecureRequest(
                    user_input="ok",
                    system_instruction="policy",
                    metadata={
                        "custom_object": object(),
                        "path": Path(tmpdir),
                    },
                ),
                risk=RiskAssessment(score=0, blocked=False),
                decision=PolicyDecision(status="allow", reasons=["ok"]),
                output_validation=OutputValidation(passed=True),
                response_text="Resposta segura",
                tool_call=None,
                tool_result=None,
            )

            payload = json.loads(log_path.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["event_id"], event_id)
        self.assertIsInstance(payload["metadata"]["custom_object"], str)
        self.assertIsInstance(payload["metadata"]["path"], str)


if __name__ == "__main__":
    unittest.main()
