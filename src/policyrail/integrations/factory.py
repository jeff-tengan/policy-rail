from __future__ import annotations

import os

from ..core.classifiers import LightweightNLPClassifier, PreflightClassifier
from .anthropic_classifier import AnthropicPreflightClassifier
from .azure_openai_classifier import AzureOpenAIPreflightClassifier
from .base import DEFAULT_LLM_JUDGE_SYSTEM_PROMPT
from .bedrock_classifier import BedrockPreflightClassifier
from .google_genai_classifier import GoogleGenAIPreflightClassifier
from .openai_classifier import OpenAIPreflightClassifier


def build_preflight_classifier(
    provider: str,
    *,
    model: str | None = None,
    system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
    fallback_classifier: PreflightClassifier | None = None,
    **provider_kwargs: object,
) -> PreflightClassifier:
    normalized = provider.strip().casefold()

    if normalized in {"lightweight", "local", "default"}:
        return LightweightNLPClassifier()
    if normalized in {"openai"}:
        return OpenAIPreflightClassifier.from_env(
            model=model,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
            **provider_kwargs,
        )
    if normalized in {"azure", "azure-openai", "azure_openai"}:
        return AzureOpenAIPreflightClassifier.from_env(
            model=model,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
            **provider_kwargs,
        )
    if normalized in {"anthropic", "claude"}:
        return AnthropicPreflightClassifier.from_env(
            model=model,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
            **provider_kwargs,
        )
    if normalized in {"google", "google-genai", "gemini"}:
        return GoogleGenAIPreflightClassifier.from_env(
            model=model,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
            **provider_kwargs,
        )
    if normalized in {"bedrock", "aws", "aws-bedrock"}:
        return BedrockPreflightClassifier.from_env(
            model=model,
            system_prompt=system_prompt,
            fallback_classifier=fallback_classifier,
            **provider_kwargs,
        )

    raise ValueError(f"Provedor de preflight nao suportado: {provider}")


def build_preflight_classifier_from_env(
    *,
    provider_env_var: str = "POLICYRAIL_PREFLIGHT_PROVIDER",
    model_env_var: str = "POLICYRAIL_PREFLIGHT_MODEL",
    default_provider: str = "lightweight",
    system_prompt: str = DEFAULT_LLM_JUDGE_SYSTEM_PROMPT,
    fallback_classifier: PreflightClassifier | None = None,
    **provider_kwargs: object,
) -> PreflightClassifier:
    provider = os.getenv(provider_env_var, default_provider)
    model = os.getenv(model_env_var) or None
    return build_preflight_classifier(
        provider,
        model=model,
        system_prompt=system_prompt,
        fallback_classifier=fallback_classifier,
        **provider_kwargs,
    )
