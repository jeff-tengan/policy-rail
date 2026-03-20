from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from policyrail.core.models import RiskAssessment, ToolCall, ToolSpec
from policyrail.core.policies import PolicyEngine
from policyrail.core.validators import OutputValidator


class PolicyAndValidationTests(unittest.TestCase):
    def test_sensitive_tool_requires_review(self) -> None:
        engine = PolicyEngine(
            [
                ToolSpec(
                    name="send_email",
                    description="Envia email",
                    sensitive=True,
                    requires_human_approval=True,
                    max_risk_score=5,
                )
            ]
        )

        decision = engine.evaluate(
            RiskAssessment(score=0, blocked=False),
            ToolCall(name="send_email", arguments={"to": "ops@example.com"}),
        )

        self.assertEqual(decision.status, "review")
        self.assertFalse(decision.allow_tool_execution)

    def test_output_validator_redacts_api_key(self) -> None:
        validator = OutputValidator()
        validation = validator.validate("Token encontrado: sk-ABCDEFGHIJKLMNOPQRSTUV123456")

        self.assertFalse(validation.passed)
        self.assertIn("Possivel vazamento de API key.", validation.violations)
        self.assertIn("[REDACTED:API_KEY]", validation.redacted_text)


if __name__ == "__main__":
    unittest.main()
