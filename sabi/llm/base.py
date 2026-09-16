"""The LLM interface every provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    cost_is_estimated: bool = False
    latency_ms: int = 0
    stop_reason: str | None = None
    meta: dict = field(default_factory=dict)


class LLMClient(ABC):
    provider: str

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 700,
        temperature: float | None = None,
    ) -> LLMResponse:
        ...

    def available(self) -> bool:
        return True


class LLMUnavailable(RuntimeError):
    """Raised when the provider cannot serve, so the caller degrades visibly."""
