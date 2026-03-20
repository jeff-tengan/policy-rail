from __future__ import annotations

import os
from typing import Any

from .base import DEFAULT_LLM_JUDGE_SYSTEM_PROMPT
from .openai_compatible import OpenAICompatiblePreflightClassifier
from ..core.classifiers import PreflightClassifier


class AzureOpenAIPreflightClassifier(OpenAICompatiblePreflightClassifier):
    def __init__(
        self,
        *,
        api_key: Any | None = None,
        base_url: str | None = None,
        model: str = "gpt-4.1-mini",
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
        use_entra_id: bool = False,
        token_provider: Any | None = None,
    ) -> None:
        super().__init__(
            model=model,
            provider_name="Azure OpenAI",
            client=client,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )
        self.api_key = api_key
        self.base_url = base_url
        self.use_entra_id = use_entra_id
        self.token_provider = token_provider

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env_var: str = "AZURE_OPENAI_API_KEY",
        base_url_env_var: str = "AZURE_OPENAI_BASE_URL",
        endpoint_env_var: str = "AZURE_OPENAI_ENDPOINT",
        deployment_env_var: str = "AZURE_OPENAI_DEPLOYMENT",
        model: str | None = None,
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
        use_entra_id_env_var: str = "AZURE_OPENAI_USE_ENTRA_ID",
    ) -> "AzureOpenAIPreflightClassifier":
        endpoint = os.getenv(endpoint_env_var, "").strip()
        base_url = os.getenv(base_url_env_var, "").strip()
        if not base_url and endpoint:
            base_url = endpoint.rstrip("/") + "/openai/v1/"

        use_entra_id = os.getenv(use_entra_id_env_var, "").strip().casefold() in {
            "1",
            "true",
            "yes",
        }

        return cls(
            api_key=os.getenv(api_key_env_var),
            base_url=base_url or None,
            model=model or os.getenv(deployment_env_var, "gpt-4.1-mini"),
            client=client,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
            use_entra_id=use_entra_id,
        )

    def _build_client(self) -> Any | None:
        if self.client is not None:
            return self.client
        if not self.base_url:
            return None

        api_key: Any | None = self.api_key
        if self.use_entra_id:
            api_key = self.token_provider or self._build_entra_token_provider()

        if api_key is None:
            return None

        try:
            from openai import OpenAI
        except ImportError:
            return None

        return OpenAI(api_key=api_key, base_url=self.base_url)

    @staticmethod
    def _build_entra_token_provider() -> Any | None:
        try:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        except ImportError:
            return None

        return get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
