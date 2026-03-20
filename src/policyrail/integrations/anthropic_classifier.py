from __future__ import annotations

import os
from typing import Any

from .base import DEFAULT_LLM_JUDGE_SYSTEM_PROMPT, RemoteJudgePreflightClassifier
from ..core.classifiers import PreflightClassifier


class AnthropicPreflightClassifier(RemoteJudgePreflightClassifier):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-3-5-haiku-latest",
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
    ) -> None:
        super().__init__(
            model=model,
            provider_name="Anthropic",
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )
        self.api_key = api_key
        self.client = client

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env_var: str = "ANTHROPIC_API_KEY",
        model_env_var: str = "ANTHROPIC_MODEL",
        model: str | None = None,
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
    ) -> "AnthropicPreflightClassifier":
        return cls(
            api_key=os.getenv(api_key_env_var),
            model=model or os.getenv(model_env_var, "claude-3-5-haiku-latest"),
            client=client,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )

    def _request_verdict(self, text: str) -> str:
        client = self.client or self._build_client()
        if client is None:
            raise RuntimeError("cliente remoto nao configurado")

        response = client.messages.create(
            model=self.model,
            max_tokens=10,
            temperature=0.0,
            system=self.system_prompt,
            messages=[{"role": "user", "content": text}],
        )

        chunks: list[str] = []
        for item in getattr(response, "content", []):
            candidate = getattr(item, "text", "")
            if candidate:
                chunks.append(candidate)
        return " ".join(chunks).strip()

    def _build_client(self) -> Any | None:
        if self.client is not None:
            return self.client
        if not self.api_key:
            return None

        try:
            import anthropic
        except ImportError:
            return None

        return anthropic.Anthropic(api_key=self.api_key)
