from __future__ import annotations

import os
from typing import Any

from .base import DEFAULT_LLM_JUDGE_SYSTEM_PROMPT, RemoteJudgePreflightClassifier
from ..core.classifiers import PreflightClassifier


class GoogleGenAIPreflightClassifier(RemoteJudgePreflightClassifier):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
        vertexai: bool = False,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            provider_name="Google Gen AI",
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )
        self.api_key = api_key
        self.client = client
        self.vertexai = vertexai
        self.project = project
        self.location = location

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env_var: str = "GEMINI_API_KEY",
        model_env_var: str = "GOOGLE_GENAI_MODEL",
        vertex_env_var: str = "GOOGLE_GENAI_USE_VERTEXAI",
        project_env_var: str = "GOOGLE_CLOUD_PROJECT",
        location_env_var: str = "GOOGLE_CLOUD_LOCATION",
        model: str | None = None,
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
    ) -> "GoogleGenAIPreflightClassifier":
        return cls(
            api_key=os.getenv(api_key_env_var),
            model=model or os.getenv(model_env_var, "gemini-2.5-flash"),
            client=client,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
            vertexai=os.getenv(vertex_env_var, "").strip().casefold() in {"1", "true", "yes"},
            project=os.getenv(project_env_var),
            location=os.getenv(location_env_var),
        )

    def _request_verdict(self, text: str) -> str:
        client = self.client or self._build_client()
        if client is None:
            raise RuntimeError("cliente remoto nao configurado")

        try:
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("SDK do Google Gen AI nao disponivel") from exc

        response = client.models.generate_content(
            model=self.model,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.0,
                max_output_tokens=10,
            ),
        )
        return getattr(response, "text", "").strip()

    def _build_client(self) -> Any | None:
        if self.client is not None:
            return self.client

        try:
            from google import genai
        except ImportError:
            return None

        client_kwargs: dict[str, Any] = {}
        if self.vertexai:
            client_kwargs["vertexai"] = True
            if self.project:
                client_kwargs["project"] = self.project
            if self.location:
                client_kwargs["location"] = self.location
        elif self.api_key:
            client_kwargs["api_key"] = self.api_key

        return genai.Client(**client_kwargs)
