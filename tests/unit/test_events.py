from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from policyrail.observability.events import AuditEvent, EventEmitter, InMemoryEventEmitter


class AuditEventTests(unittest.TestCase):
    def test_default_fields(self) -> None:
        event = AuditEvent()
        self.assertTrue(event.event_id)
        self.assertTrue(event.timestamp)
        self.assertEqual(event.risk_score, 0)
        self.assertFalse(event.risk_blocked)
        self.assertTrue(event.output_passed)

    def test_fields_propagate(self) -> None:
        event = AuditEvent(
            risk_score=75,
            risk_blocked=True,
            decision="block",
            decision_reasons=["Score too high"],
            tool_name="send_email",
            sanitization_applied=True,
            sanitization_rules=["instruction_override_en"],
        )
        self.assertEqual(event.risk_score, 75)
        self.assertTrue(event.risk_blocked)
        self.assertEqual(event.decision, "block")
        self.assertEqual(event.tool_name, "send_email")
        self.assertTrue(event.sanitization_applied)
        self.assertEqual(event.sanitization_rules, ["instruction_override_en"])


class EventEmitterProtocolTests(unittest.TestCase):
    def test_in_memory_emitter_implements_protocol(self) -> None:
        emitter = InMemoryEventEmitter()
        self.assertIsInstance(emitter, EventEmitter)

    def test_in_memory_emitter_collects_events(self) -> None:
        emitter = InMemoryEventEmitter()
        event = AuditEvent(risk_score=42, decision="review")
        emitter.emit(event)
        self.assertEqual(len(emitter.events), 1)
        self.assertEqual(emitter.events[0].risk_score, 42)

    def test_multiple_emitters(self) -> None:
        emitter_a = InMemoryEventEmitter()
        emitter_b = InMemoryEventEmitter()
        event = AuditEvent(decision="allow")

        for emitter in [emitter_a, emitter_b]:
            emitter.emit(event)

        self.assertEqual(len(emitter_a.events), 1)
        self.assertEqual(len(emitter_b.events), 1)

    def test_custom_emitter_adheres_to_protocol(self) -> None:
        class CounterEmitter:
            def __init__(self) -> None:
                self.count = 0

            def emit(self, event: AuditEvent) -> None:
                self.count += 1

        emitter = CounterEmitter()
        self.assertIsInstance(emitter, EventEmitter)
        emitter.emit(AuditEvent())
        self.assertEqual(emitter.count, 1)


if __name__ == "__main__":
    unittest.main()
