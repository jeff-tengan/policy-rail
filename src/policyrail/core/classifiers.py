from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

ClassificationLabel = Literal["malicious", "benign"]


@dataclass(frozen=True, slots=True)
class ClassificationSignal:
    signal_id: str
    description: str
    keywords: tuple[str, ...]
    weight: float


@dataclass(slots=True)
class PreflightClassification:
    label: ClassificationLabel
    malicious_probability: float
    summary: str
    matched_signals: list[str]
    model_name: str


class PreflightClassifier(Protocol):
    def classify(self, text: str) -> PreflightClassification:
        ...


def _default_malicious_signals() -> list[ClassificationSignal]:
    return [
        ClassificationSignal(
            signal_id="ignore_instructions_pt",
            description="Pedido para ignorar instrucoes existentes.",
            keywords=("ignore", "instrucoes"),
            weight=1.35,
        ),
        ClassificationSignal(
            signal_id="ignore_instructions_en",
            description="Pedido para ignorar instructions do sistema.",
            keywords=("ignore", "instructions"),
            weight=1.35,
        ),
        ClassificationSignal(
            signal_id="reveal_prompt_pt",
            description="Tentativa de revelar prompt interno ou segredo.",
            keywords=("mostre", "prompt"),
            weight=1.45,
        ),
        ClassificationSignal(
            signal_id="reveal_secret_en",
            description="Tentativa de revelar secret ou system prompt.",
            keywords=("reveal", "secret"),
            weight=1.45,
        ),
        ClassificationSignal(
            signal_id="bypass_policy",
            description="Tentativa de contornar policy ou seguranca.",
            keywords=("bypass", "policy"),
            weight=1.15,
        ),
        ClassificationSignal(
            signal_id="disable_security_pt",
            description="Tentativa de desativar filtros ou seguranca.",
            keywords=("desative", "seguranca"),
            weight=1.15,
        ),
        ClassificationSignal(
            signal_id="tool_execution_en",
            description="Tentativa de induzir execucao de tool.",
            keywords=("run", "tool"),
            weight=0.95,
        ),
        ClassificationSignal(
            signal_id="tool_execution_pt",
            description="Tentativa de induzir execucao de ferramenta.",
            keywords=("rode", "ferramenta"),
            weight=0.95,
        ),
        ClassificationSignal(
            signal_id="role_escalation_en",
            description="Tentativa de assumir papel privilegiado.",
            keywords=("act", "system"),
            weight=1.05,
        ),
        ClassificationSignal(
            signal_id="role_escalation_pt",
            description="Tentativa de escalar privilegio ou papel.",
            keywords=("aja", "admin"),
            weight=1.05,
        ),
        ClassificationSignal(
            signal_id="encoding_obfuscation",
            description="Uso de encoding ou ofuscacao no prompt.",
            keywords=("base64",),
            weight=0.7,
        ),
        ClassificationSignal(
            signal_id="encoding_rot13",
            description="Uso de transformacao de texto para esconder instrucao.",
            keywords=("rot13",),
            weight=0.7,
        ),
    ]


def _default_safe_signals() -> list[ClassificationSignal]:
    return [
        ClassificationSignal(
            signal_id="policy_lookup",
            description="Pergunta legitima sobre politica ou processo.",
            keywords=("politica",),
            weight=0.55,
        ),
        ClassificationSignal(
            signal_id="documentation_lookup",
            description="Pedido legitimo de documentacao oficial.",
            keywords=("documentacao", "oficial"),
            weight=0.8,
        ),
        ClassificationSignal(
            signal_id="summarization",
            description="Pedido legitimo de resumo ou explicacao.",
            keywords=("resuma",),
            weight=0.5,
        ),
        ClassificationSignal(
            signal_id="explanation",
            description="Pedido legitimo de explicacao.",
            keywords=("explique",),
            weight=0.4,
        ),
    ]


class LightweightNLPClassifier:
    def __init__(
        self,
        *,
        malicious_signals: list[ClassificationSignal] | None = None,
        safe_signals: list[ClassificationSignal] | None = None,
        malicious_threshold: float = 0.55,
        bias: float = -2.4,
        model_name: str = "lightweight-nlp-preflight",
    ) -> None:
        self.malicious_signals = list(malicious_signals or _default_malicious_signals())
        self.safe_signals = list(safe_signals or _default_safe_signals())
        self.malicious_threshold = malicious_threshold
        self.bias = bias
        self.model_name = model_name

    def classify(self, text: str) -> PreflightClassification:
        normalized = self._normalize(text)
        if not normalized:
            return PreflightClassification(
                label="benign",
                malicious_probability=0.0,
                summary="Classificador NLP nao encontrou indicios relevantes.",
                matched_signals=[],
                model_name=self.model_name,
            )

        token_set = set(normalized.split())
        raw_score = self.bias
        matched_signals: list[str] = []

        for signal in self.malicious_signals:
            if self._matches(signal, token_set):
                raw_score += signal.weight
                matched_signals.append(signal.description)

        for signal in self.safe_signals:
            if self._matches(signal, token_set):
                raw_score -= signal.weight

        malicious_probability = round(self._sigmoid(raw_score), 4)
        label: ClassificationLabel = (
            "malicious" if malicious_probability >= self.malicious_threshold else "benign"
        )

        if label == "malicious":
            summary = "Classificador NLP classificou o texto como malicioso no preflight."
        elif matched_signals or malicious_probability >= 0.25:
            summary = "Classificador NLP encontrou sinais residuais de risco no preflight."
        else:
            summary = "Classificador NLP nao encontrou indicios relevantes."

        return PreflightClassification(
            label=label,
            malicious_probability=malicious_probability,
            summary=summary,
            matched_signals=list(dict.fromkeys(matched_signals)),
            model_name=self.model_name,
        )

    def _matches(self, signal: ClassificationSignal, token_set: set[str]) -> bool:
        return all(keyword in token_set for keyword in signal.keywords)

    @staticmethod
    def _normalize(text: str) -> str:
        folded = unicodedata.normalize("NFKD", text.casefold())
        without_accents = "".join(char for char in folded if not unicodedata.combining(char))
        normalized_chars: list[str] = []
        for char in without_accents:
            if char.isalnum() or char.isspace():
                normalized_chars.append(char)
            else:
                normalized_chars.append(" ")
        return " ".join("".join(normalized_chars).split())

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))


class CallablePreflightClassifier:
    def __init__(
        self,
        classifier_fn: Callable[[str], PreflightClassification],
        *,
        model_name: str = "custom-mini-llm-classifier",
    ) -> None:
        self.classifier_fn = classifier_fn
        self.model_name = model_name

    def classify(self, text: str) -> PreflightClassification:
        result = self.classifier_fn(text)
        if result.model_name:
            return result
        return PreflightClassification(
            label=result.label,
            malicious_probability=result.malicious_probability,
            summary=result.summary,
            matched_signals=result.matched_signals,
            model_name=self.model_name,
        )
