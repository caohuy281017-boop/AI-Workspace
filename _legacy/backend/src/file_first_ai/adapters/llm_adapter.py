"""Multi-provider LLM Gateway Adapter.

Implements the ``LLMProvider`` port for three backends:
  - Google Gemini (default, via ``google-generativeai`` SDK)
  - OpenAI-compatible (via ``openai`` SDK — covers OpenAI and local Ollama/LM Studio)

Configuration is driven by environment variables so no vendor code leaks
into application or domain layers.

Environment variables:

  LLM_PROVIDER          One of: "gemini" | "openai" | "openai_compatible"
                         Defaults to "gemini".

  GEMINI_API_KEY        Required when provider is "gemini".
  GEMINI_MODEL          Gemini model name. Default: "gemini-1.5-flash".

  OPENAI_API_KEY        Required when provider is "openai".
  OPENAI_MODEL          OpenAI model name. Default: "gpt-4o-mini".

  OPENAI_BASE_URL       Override base URL for openai_compatible (Ollama etc.).
                         Default: "http://localhost:11434/v1"
  OPENAI_COMPATIBLE_MODEL  Model name for openai_compatible provider.

GitNexus boundary: only ``adapters/`` may import vendor SDKs.
Domain and ports layers must never import from this module directly.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from file_first_ai.domain import LLMMessage, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider constants
# ---------------------------------------------------------------------------

PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"

_DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_OLLAMA_MODEL = "llama3"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _messages_to_text(messages: list[LLMMessage]) -> str:
    """Flatten LLM messages into a plain text block for single-turn providers."""
    return "\n\n".join(f"[{m.role.upper()}]\n{m.content}" for m in messages)


def _call_gemini(
    messages: list[LLMMessage],
    response_schema: dict[str, Any] | None,
    api_key: str,
    model_name: str,
) -> LLMResponse:
    try:
        import google.generativeai as genai  # type: ignore[import]
        from google.generativeai.types import GenerationConfig  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "google-generativeai is required for the Gemini provider. "
            "Install it with: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)

    gen_config_kwargs: dict[str, Any] = {"temperature": 0}
    if response_schema:
        gen_config_kwargs["response_mime_type"] = "application/json"

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=GenerationConfig(**gen_config_kwargs),
    )

    prompt = _messages_to_text(messages)
    if response_schema:
        prompt += f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_schema, indent=2)}"

    response = model.generate_content(prompt)
    raw_text: str = response.text or ""

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None)
    output_tokens = getattr(usage, "candidates_token_count", None)

    return LLMResponse(
        content=raw_text,
        provider=PROVIDER_GEMINI,
        model=model_name,
        finish_reason=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _call_openai_compatible(
    messages: list[LLMMessage],
    response_schema: dict[str, Any] | None,
    api_key: str,
    model_name: str,
    base_url: str | None,
    provider_label: str,
) -> LLMResponse:
    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai package is required for OpenAI / OpenAI-compatible providers. "
            "Install it with: pip install openai"
        ) from exc

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)

    openai_messages = [{"role": m.role, "content": m.content} for m in messages]

    call_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": openai_messages,
        "temperature": 0,
    }

    if response_schema:
        call_kwargs["response_format"] = {"type": "json_object"}

    completion = client.chat.completions.create(**call_kwargs)
    choice = completion.choices[0]
    raw_text: str = choice.message.content or ""

    return LLMResponse(
        content=raw_text,
        provider=provider_label,
        model=model_name,
        finish_reason=choice.finish_reason,
        input_tokens=completion.usage.prompt_tokens if completion.usage else None,
        output_tokens=completion.usage.completion_tokens if completion.usage else None,
    )


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------

class MultiProviderLLMAdapter:
    """``LLMProvider`` implementation that dispatches to the configured backend.

    Select the backend via ``LLM_PROVIDER`` environment variable.
    Instantiate once and inject via dependency injection into adapters that
    implement ``LLMProvider``.
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        gemini_api_key: str | None = None,
        gemini_model: str | None = None,
        openai_api_key: str | None = None,
        openai_model: str | None = None,
        openai_base_url: str | None = None,
        openai_compatible_model: str | None = None,
    ) -> None:
        self._provider = (
            provider
            or os.environ.get("LLM_PROVIDER", PROVIDER_GEMINI)
        ).lower()

        # Gemini settings
        self._gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self._gemini_model = gemini_model or os.environ.get("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL)

        # OpenAI settings
        self._openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        self._openai_model = openai_model or os.environ.get("OPENAI_MODEL", _DEFAULT_OPENAI_MODEL)

        # OpenAI-compatible (Ollama / LM Studio) settings
        self._openai_base_url = (
            openai_base_url
            or os.environ.get("OPENAI_BASE_URL", _DEFAULT_OLLAMA_BASE_URL)
        )
        self._openai_compatible_model = (
            openai_compatible_model
            or os.environ.get("OPENAI_COMPATIBLE_MODEL", _DEFAULT_OLLAMA_MODEL)
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Dispatch to the configured provider and return a neutral LLMResponse."""
        logger.info("LLM request via provider=%s model=%s", self._provider, self._effective_model)

        if self._provider == PROVIDER_GEMINI:
            return _call_gemini(
                list(request.messages),
                request.response_schema,
                api_key=self._gemini_api_key,
                model_name=self._gemini_model,
            )

        if self._provider == PROVIDER_OPENAI:
            return _call_openai_compatible(
                list(request.messages),
                request.response_schema,
                api_key=self._openai_api_key,
                model_name=self._openai_model,
                base_url=None,
                provider_label=PROVIDER_OPENAI,
            )

        if self._provider == PROVIDER_OPENAI_COMPATIBLE:
            return _call_openai_compatible(
                list(request.messages),
                request.response_schema,
                api_key=self._openai_api_key or "not-required",
                model_name=self._openai_compatible_model,
                base_url=self._openai_base_url,
                provider_label=PROVIDER_OPENAI_COMPATIBLE,
            )

        raise ValueError(
            f"Unknown LLM_PROVIDER '{self._provider}'. "
            f"Choose from: {PROVIDER_GEMINI}, {PROVIDER_OPENAI}, {PROVIDER_OPENAI_COMPATIBLE}"
        )

    @property
    def _effective_model(self) -> str:
        if self._provider == PROVIDER_GEMINI:
            return self._gemini_model
        if self._provider == PROVIDER_OPENAI:
            return self._openai_model
        return self._openai_compatible_model
