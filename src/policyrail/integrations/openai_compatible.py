from __future__ import annotations

from typing import Any

from .base import DEFAULT_LLM_JUDGE_SYSTEM_PROMPT, RemoteJudgePreflightClassifier
from ..core.classifiers import PreflightClassifier


class OpenAICompatiblePreflightClassifier(RemoteJudgePreflightClassifier):
    def __init__(
        self,
        *,
        model: str,
        provider_name: str,
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
    ) -> None:
        super().__init__(
            model=model,
            provider_name=provider_name,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )
        self.client = client

    def _request_verdict(self, text: str) -> str:
        client = self.client or self._build_client()
        if client is None:
            raise RuntimeError("cliente remoto nao configurado")

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        return ((response.choices[0].message.content or "")).strip()

    def _build_client(self) -> Any | None:
        raise NotImplementedError
