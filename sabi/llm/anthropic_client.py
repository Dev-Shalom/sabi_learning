"""Anthropic provider.

Notes on the choices here:

* The system prompt is sent as a cacheable block. It is stable across every
  request, so on the escalation model it earns a cache read; on Haiku the
  minimum cacheable prefix may not be met, in which case caching is a no-op
  rather than an error.
* Thinking: Haiku 4.5 does not take `effort`, so nothing is sent for the cheap
  path -- these are short grounded answers, not reasoning problems. Escalation
  to Sonnet 5 runs adaptive thinking at low effort: enough headroom for a
  harder question, without the latency of a long reasoning pass on a 3G phone.
* A refusal or a transport failure raises `LLMUnavailable` so the caller can
  degrade visibly instead of rendering an empty answer.
"""

from __future__ import annotations

import time

from sabi.config import settings
from sabi.llm.base import LLMClient, LLMResponse, LLMUnavailable
from sabi.llm.pricing import cost_usd

# Models that accept output_config.effort. Haiku 4.5 errors on it.
EFFORT_CAPABLE = {"claude-sonnet-5", "claude-opus-5"}


class AnthropicLLM(LLMClient):
    provider = "anthropic"

    def __init__(self, api_key: str | None = None, timeout: float = 25.0):
        import anthropic

        key = api_key or settings().anthropic_api_key
        if not key:
            raise RuntimeError(
                "SABI_ANTHROPIC_API_KEY is not set but SABI_LLM_PROVIDER=anthropic"
            )
        # Two retries is the SDK default and is right here: a student on a bad
        # connection is already waiting, and the request-level timeout caps the
        # total wall clock.
        self._client = anthropic.Anthropic(api_key=key, timeout=timeout, max_retries=2)
        self._anthropic = anthropic

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 700,
        temperature: float | None = None,
        context: list[dict] | None = None,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": user}],
        }
        if model in EFFORT_CAPABLE:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": "low"}

        started = time.perf_counter()
        try:
            resp = self._client.messages.create(**kwargs)
        except self._anthropic.RateLimitError as e:
            raise LLMUnavailable(f"rate limited: {e}") from e
        except self._anthropic.APITimeoutError as e:
            raise LLMUnavailable("the model took too long to answer") from e
        except self._anthropic.APIConnectionError as e:
            raise LLMUnavailable("could not reach the model") from e
        except self._anthropic.APIStatusError as e:
            raise LLMUnavailable(f"model error {e.status_code}") from e

        elapsed = int((time.perf_counter() - started) * 1000)

        if resp.stop_reason == "refusal":
            raise LLMUnavailable("the model declined this request")

        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

        return LLMResponse(
            text=text.strip(),
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=cost_usd(model, tokens_in, tokens_out, cache_read, cache_write),
            cost_is_estimated=False,
            latency_ms=elapsed,
            stop_reason=resp.stop_reason,
            meta={"request_id": getattr(resp, "_request_id", None)},
        )
