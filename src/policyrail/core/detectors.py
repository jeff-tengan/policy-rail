from __future__ import annotations

from .classifiers import LightweightNLPClassifier, PreflightClassifier
from .models import RiskAssessment, RiskFinding


class PromptInjectionDetector:
    def __init__(
        self,
        classifier: PreflightClassifier | None = None,
        *,
        review_threshold: int = 25,
        block_threshold: int = 60,
        degraded_review_floor: int | None = None,
    ) -> None:
        self.classifier = classifier or LightweightNLPClassifier()
        self.review_threshold = review_threshold
        self.block_threshold = block_threshold
        self.degraded_review_floor = (
            review_threshold if degraded_review_floor is None else degraded_review_floor
        )

    def detect(self, text: str, *, source: str = "user_input") -> RiskAssessment:
        if not text.strip():
            return RiskAssessment(score=0, blocked=False, findings=[], reasons=[])

        classification = self.classifier.classify(text)
        score = min(100, round(classification.malicious_probability * 100))
        if classification.degraded and score < self.degraded_review_floor:
            score = self.degraded_review_floor
        blocked = score >= self.block_threshold

        findings: list[RiskFinding] = []
        reasons: list[str] = []

        if score >= self.review_threshold or classification.matched_signals:
            findings.append(
                RiskFinding(
                    rule_id="preflight_classifier",
                    category="classifier_preflight",
                    description=classification.summary,
                    matched_text=self._clip(
                        "; ".join(classification.matched_signals) or text
                    ),
                    weight=score,
                    source=source,
                )
            )
            reasons = list(
                dict.fromkeys(
                    [classification.summary, *classification.matched_signals[:2]]
                )
            )

        return RiskAssessment(score=score, blocked=blocked, findings=findings, reasons=reasons)

    def merge(self, *assessments: RiskAssessment) -> RiskAssessment:
        findings: list[RiskFinding] = []
        reasons: list[str] = []
        total_score = 0

        for assessment in assessments:
            findings.extend(assessment.findings)
            reasons.extend(assessment.reasons)
            total_score += assessment.score

        score = min(100, total_score)
        blocked = any(assessment.blocked for assessment in assessments) or score >= self.block_threshold
        return RiskAssessment(
            score=score,
            blocked=blocked,
            findings=findings,
            reasons=list(dict.fromkeys(reasons)),
        )

    @staticmethod
    def _clip(text: str, *, max_length: int = 120) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3] + "..."
