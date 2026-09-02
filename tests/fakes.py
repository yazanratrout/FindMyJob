"""Test doubles for the LLM layer."""

from __future__ import annotations

from findmyjob.llm.client import ApiFn, LlmClient, RawCompletion


def scripted_api_fn(*responses: str, in_tokens: int = 100, out_tokens: int = 50) -> ApiFn:
    """Return an ApiFn that yields the given texts in order, then repeats the last."""
    queue = list(responses)

    def _fn(
        model: str, system: str, user: str, max_tokens: int, temperature: float
    ) -> RawCompletion:
        text = queue.pop(0) if len(queue) > 1 else queue[0]
        return RawCompletion(text=text, input_tokens=in_tokens, output_tokens=out_tokens)

    return _fn


def fake_client(*responses: str) -> LlmClient:
    return LlmClient(api_fn=scripted_api_fn(*responses))
