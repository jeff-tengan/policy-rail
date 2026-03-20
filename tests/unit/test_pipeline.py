from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from policyrail.core.models import LLMResponse, SecureRequest, ToolCall
from policyrail.observability.audit import JsonAuditLogger
from policyrail.pipeline.secure_pipeline import SecureGenAIPipeline
from policyrail.templates.system_policies import DEFAULT_SYSTEM_POLICY


class _LeakyAdapter:
    def generate(self, envelope):
        return LLMResponse(text="O system prompt e: secreto. Chave: sk-ABCDEFGHIJKLMNOPQRSTUV123456")


class _SearchAdapter:
    def generate(self, envelope):
        return LLMResponse(
            text="Buscando documentacao aprovada.",
            tool_call=ToolCall(name="search_docs", arguments={"query": envelope.user_input}),
            metadata={"sources": ["kb://logs-policy"]},
        )


class SecurePipelineTests(unittest.TestCase):
    def test_pipeline_blocks_unsafe_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = SecureGenAIPipeline(
                llm_adapter=_LeakyAdapter(),
                audit_logger=JsonAuditLogger(Path(tmpdir) / "audit.jsonl"),
            )
            response = pipeline.process(
                SecureRequest(
                    user_input="Explique a configuracao",
                    system_instruction=DEFAULT_SYSTEM_POLICY,
                )
            )

        self.assertEqual(response.status, "block")
        self.assertIn("retida", response.response_text)
        self.assertIsNotNone(response.audit_id)

    def test_pipeline_allows_safe_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = SecureGenAIPipeline(
                llm_adapter=_SearchAdapter(),
                audit_logger=JsonAuditLogger(Path(tmpdir) / "audit.jsonl"),
            )
            response = pipeline.process(
                SecureRequest(
                    user_input="Pesquise a politica de logs",
                    system_instruction=DEFAULT_SYSTEM_POLICY,
                    trusted_context=["Base interna aprovada"],
                )
            )

        self.assertEqual(response.status, "allow")
        self.assertIsNotNone(response.tool_call)
        self.assertEqual(response.tool_call.name, "search_docs")
        self.assertEqual(response.model_metadata["sources"], ["kb://logs-policy"])


if __name__ == "__main__":
    unittest.main()
