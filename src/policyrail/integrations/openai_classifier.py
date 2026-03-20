from __future__ import annotations

import os
from typing import Any

from .base import (
    DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
    DEFAULT_OPENAI_PREFLIGHT_PROMPT,
)
from .openai_compatible import OpenAICompatiblePreflightClassifier
from ..core.classifiers import PreflightClassifier


class OpenAIPreflightClassifier(OpenAICompatiblePreflightClassifier):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
    ) -> None:
        super().__init__(
            model=model,
            provider_name="OpenAI",
            client=client,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )
        self.api_key = api_key

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env_var: str = "OPENAI_API_KEY",
        model_env_var: str = "OPENAI_PREFLIGHT_MODEL",
        model: str | None = None,
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
    ) -> "OpenAIPreflightClassifier":
        return cls(
            api_key=os.getenv(api_key_env_var),
            model=model or os.getenv(model_env_var, "gpt-4o-mini"),
            client=client,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )

    def _build_client(self) -> Any | None:
        if self.client is not None:
            return self.client
        if not self.api_key:
            return None

        try:
            from openai import OpenAI
        except ImportError:
            return None

        return OpenAI(api_key=self.api_key)
