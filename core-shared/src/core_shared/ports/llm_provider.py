from __future__ import annotations

from typing import Protocol

from core_shared.domain import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    """Provider-neutral entry point implemented by the LLM gateway."""

    def complete(self, request: LLMRequest) -> LLMResponse: ...
