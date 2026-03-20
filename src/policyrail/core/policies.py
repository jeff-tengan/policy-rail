from __future__ import annotations

from .models import PolicyDecision, RiskAssessment, ToolCall, ToolSpec


class PolicyEngine:
    def __init__(
        self,
        tool_specs: list[ToolSpec] | None = None,
        *,
        review_threshold: int = 25,
        block_threshold: int = 60,
    ) -> None:
        self.tool_specs = {tool.name: tool for tool in tool_specs or []}
        self.review_threshold = review_threshold
        self.block_threshold = block_threshold

    def evaluate(
        self,
        risk: RiskAssessment,
        tool_call: ToolCall | None = None,
    ) -> PolicyDecision:
        reasons = list(risk.reasons)

        if risk.score >= self.block_threshold or risk.blocked:
            reasons.append("Score de risco acima do limite de bloqueio.")
            return PolicyDecision(status="block", reasons=self._dedupe(reasons), allow_tool_execution=False)

        base_status = "allow"
        if risk.score >= self.review_threshold:
            base_status = "review"
            reasons.append("Score de risco acima do limite de revisao.")

        if tool_call is None:
            if not reasons:
                reasons.append("Nenhum risco relevante detectado.")
            return PolicyDecision(status=base_status, reasons=self._dedupe(reasons), allow_tool_execution=False)

        tool_spec = self.tool_specs.get(tool_call.name)
        if tool_spec is None:
            reasons.append(f"Tool '{tool_call.name}' nao esta na allowlist.")
            return PolicyDecision(status="block", reasons=self._dedupe(reasons), allow_tool_execution=False)

        if tool_spec.requires_human_approval:
            reasons.append(f"Tool '{tool_call.name}' exige aprovacao humana.")
            return PolicyDecision(status="review", reasons=self._dedupe(reasons), allow_tool_execution=False)

        if tool_spec.sensitive and risk.score > 0:
            reasons.append(f"Tool sensivel '{tool_call.name}' retida por risco residual.")
            return PolicyDecision(status="review", reasons=self._dedupe(reasons), allow_tool_execution=False)

        if risk.score > tool_spec.max_risk_score:
            reasons.append(
                f"Score {risk.score} excede o limite permitido para '{tool_call.name}'."
            )
            return PolicyDecision(status="review", reasons=self._dedupe(reasons), allow_tool_execution=False)

        reasons.append(f"Tool '{tool_call.name}' aprovada pela allowlist.")
        return PolicyDecision(status=base_status, reasons=self._dedupe(reasons), allow_tool_execution=True)

    @staticmethod
    def _dedupe(reasons: list[str]) -> list[str]:
        return list(dict.fromkeys(reasons))
