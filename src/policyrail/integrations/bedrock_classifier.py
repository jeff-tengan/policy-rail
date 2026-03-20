from __future__ import annotations

import os
from typing import Any

from .base import DEFAULT_LLM_JUDGE_SYSTEM_PROMPT, RemoteJudgePreflightClassifier
from ..core.classifiers import PreflightClassifier


class BedrockPreflightClassifier(RemoteJudgePreflightClassifier):
    def __init__(
        self,
        *,
        model: str = "amazon.titan-text-express-v1",
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
        region_name: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            provider_name="Amazon Bedrock",
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )
        self.client = client
        self.region_name = region_name

    @classmethod
    def from_env(
        cls,
        *,
        model_env_var: str = "BEDROCK_MODEL_ID",
        region_env_var: str = "AWS_REGION",
        model: str | None = None,
        client: Any | None = None,
        system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
        fallback_classifier: PreflightClassifier | None = None,
    ) -> "BedrockPreflightClassifier":
        return cls(
            model=model or os.getenv(model_env_var, "amazon.titan-text-express-v1"),
            client=client,
            region_name=os.getenv(region_env_var) or os.getenv("AWS_DEFAULT_REGION"),
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
        )

    def _request_verdict(self, text: str) -> str:
        client = self.client or self._build_client()
        if client is None:
            raise RuntimeError("cliente remoto nao configurado")

        response = client.converse(
            modelId=self.model,
            system=[{"text": self.system_prompt}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": text}],
                }
            ],
            inferenceConfig={"temperature": 0.0, "maxTokens": 10},
        )
        content_items = response["output"]["message"]["content"]
        texts = [item.get("text", "") for item in content_items if item.get("text")]
        return " ".join(texts).strip()

    def _build_client(self) -> Any | None:
        if self.client is not None:
            return self.client

        try:
            import boto3
        except ImportError:
            return None

        client_kwargs: dict[str, Any] = {"service_name": "bedrock-runtime"}
        if self.region_name:
            client_kwargs["region_name"] = self.region_name
        return boto3.client(**client_kwargs)
