"""Send a prompt to an OpenAI-compatible LLM API and return the completion text."""
from __future__ import annotations

import json
import os
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o"


def call_llm(
    prompt: str,
    *,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    top_p: float = 0.9,
    max_tokens: int = 4096,
) -> str:
    """
    Send *prompt* to an OpenAI-compatible chat completion endpoint.

    Configuration is resolved in this priority order:
    1. Explicit keyword arguments.
    2. Environment variables: OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL.
    3. Hardcoded defaults (api.openai.com / gpt-4o).

    Parameters
    ----------
    prompt:
        User-role message content.
    system_prompt:
        Optional system-role message prepended to the conversation.
    temperature:
        Sampling temperature (default 0.2 — favours focused, factual output).
    top_p:
        Nucleus sampling probability mass (default 0.9).

    Returns the assistant's response text.
    Raises RuntimeError on API or network errors.
    """
    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not resolved_api_key:
        raise RuntimeError(
            "No API key provided. Set OPENAI_API_KEY or pass api_key= explicitly."
        )

    resolved_base_url = (
        base_url
        or os.environ.get("OPENAI_BASE_URL", _DEFAULT_BASE_URL)
    ).rstrip("/")
    resolved_model = model or os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)

    url = f"{resolved_base_url}/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": resolved_model,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {resolved_api_key}",
    }

    req = Request(url, data=body, headers=headers, method="POST")  # noqa: S310

    try:
        with urlopen(req, timeout=120) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"LLM API returned HTTP {exc.code}: {error_body}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling LLM API: {exc.reason}") from exc

    data = json.loads(raw)

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"Unexpected LLM API response shape: {raw[:500]}"
        ) from exc
