from __future__ import annotations

import re
from dataclasses import dataclass

from .models import OutputValidation


@dataclass(frozen=True, slots=True)
class OutputRule:
    rule_id: str
    description: str
    pattern: re.Pattern[str]
    replacement: str
    blocking: bool = True


def _default_rules() -> list[OutputRule]:
    return [
        OutputRule(
            rule_id="openai_api_key",
            description="Possivel vazamento de API key.",
            pattern=re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
            replacement="[REDACTED:API_KEY]",
        ),
        OutputRule(
            rule_id="aws_access_key",
            description="Possivel vazamento de credencial AWS.",
            pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            replacement="[REDACTED:AWS_KEY]",
        ),
        OutputRule(
            rule_id="credit_card",
            description="Possivel vazamento de numero de cartao.",
            pattern=re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
            replacement="[REDACTED:CARD]",
        ),
        OutputRule(
            rule_id="private_prompt",
            description="Possivel vazamento de prompt interno.",
            pattern=re.compile(
                r"(system prompt|prompt interno|prompt oculto).{0,24}(?:e|:)",
                re.IGNORECASE,
            ),
            replacement="[REDACTED:PROMPT]",
        ),
    ]


class OutputValidator:
    def __init__(self, rules: list[OutputRule] | None = None) -> None:
        self.rules = list(rules or _default_rules())

    def validate(self, text: str) -> OutputValidation:
        redacted_text = text
        violations: list[str] = []
        blocking_hits = 0

        for rule in self.rules:
            if rule.pattern.search(redacted_text):
                violations.append(rule.description)
                redacted_text = rule.pattern.sub(rule.replacement, redacted_text)
                if rule.blocking:
                    blocking_hits += 1

        return OutputValidation(
            passed=blocking_hits == 0,
            violations=list(dict.fromkeys(violations)),
            redacted_text=redacted_text,
        )
