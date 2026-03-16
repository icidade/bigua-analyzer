"""Send prompts to LLM providers and return the completion text."""
from __future__ import annotations

import json
import os
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_OPENAI_MODEL = "gpt-4o"
_DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
_DEFAULT_XAI_MODEL = "grok-2-latest"
_DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
_DEFAULT_OLLAMA_MODEL = "llama3.1"


def _http_json(
    *,
    url: str,
    payload: dict,
    headers: Optional[dict[str, str]] = None,
    timeout: int = 120,
) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers=headers or {}, method="POST")  # noqa: S310

    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"LLM API returned HTTP {exc.code}: {error_body}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling LLM API: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from LLM API: {raw[:500]}") from exc


def _get_required_api_key(
    provider: str,
    explicit_api_key: Optional[str],
) -> str:
    if explicit_api_key:
        return explicit_api_key

    env_candidates = {
        "openai": ["LLM_API_KEY", "OPENAI_API_KEY"],
        "openai-compatible": ["LLM_API_KEY", "OPENAI_API_KEY"],
        "xai": ["XAI_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"],
    }.get(provider, [])

    for env_name in env_candidates:
        value = os.environ.get(env_name)
        if value:
            return value

    if provider == "ollama":
        return ""

    expected = ", ".join(env_candidates) if env_candidates else "LLM_API_KEY"
    raise RuntimeError(
        f"No API key provided for provider '{provider}'. "
        f"Set one of: {expected}, or pass --api-key."
    )


def _resolve_base_url(provider: str, base_url: Optional[str]) -> str:
    if base_url:
        return base_url.rstrip("/")

    generic = os.environ.get("LLM_BASE_URL")
    if generic:
        return generic.rstrip("/")

    if provider in {"openai", "openai-compatible"}:
        return os.environ.get("OPENAI_BASE_URL", _DEFAULT_OPENAI_BASE_URL).rstrip("/")
    if provider == "xai":
        return os.environ.get("XAI_BASE_URL", _DEFAULT_XAI_BASE_URL).rstrip("/")
    if provider == "gemini":
        return os.environ.get("GEMINI_BASE_URL", _DEFAULT_GEMINI_BASE_URL).rstrip("/")
    if provider == "ollama":
        return os.environ.get("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE_URL).rstrip("/")

    raise RuntimeError(f"Unsupported provider: {provider}")


def _resolve_model(provider: str, model: Optional[str]) -> str:
    if model:
        return model

    generic = os.environ.get("LLM_MODEL")
    if generic:
        return generic

    if provider in {"openai", "openai-compatible"}:
        return os.environ.get("OPENAI_MODEL", _DEFAULT_OPENAI_MODEL)
    if provider == "xai":
        return os.environ.get("XAI_MODEL", _DEFAULT_XAI_MODEL)
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL)
    if provider == "ollama":
        return os.environ.get("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL)

    raise RuntimeError(f"Unsupported provider: {provider}")


def _call_openai_compatible(
    *,
    provider: str,
    prompt: str,
    system_prompt: Optional[str],
    model: str,
    base_url: str,
    api_key: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> str:
    url = f"{base_url}/chat/completions"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = _http_json(url=url, payload=payload, headers=headers)

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"Unexpected response shape from provider '{provider}': {str(data)[:500]}"
        ) from exc


def _call_gemini(
    *,
    prompt: str,
    system_prompt: Optional[str],
    model: str,
    base_url: str,
    api_key: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
) -> str:
    url = f"{base_url}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    headers = {"Content-Type": "application/json"}
    data = _http_json(url=url, payload=payload, headers=headers)

    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected response shape from provider 'gemini': {str(data)[:500]}") from exc


def _call_ollama(
    *,
    prompt: str,
    system_prompt: Optional[str],
    model: str,
    base_url: str,
    temperature: float,
    top_p: float,
) -> str:
    url = f"{base_url}/api/chat"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
        },
    }
    headers = {"Content-Type": "application/json"}
    data = _http_json(url=url, payload=payload, headers=headers)

    try:
        return data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected response shape from provider 'ollama': {str(data)[:500]}") from exc


def call_llm(
    prompt: str,
    *,
    provider: str = "openai-compatible",
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    top_p: float = 0.9,
    max_tokens: int = 4096,
) -> str:
    """
    Send *prompt* to a provider-specific LLM API.

    Supported providers:
    - ``openai-compatible`` (default)
    - ``openai``
    - ``xai``
    - ``gemini``
    - ``ollama``

    Configuration is resolved in this priority order when relevant:
    1. Explicit keyword arguments.
    2. Provider-specific environment variables.
    3. Hardcoded defaults.

    Parameters
    ----------
    prompt:
        User-role message content.
    provider:
        LLM provider adapter name.
    system_prompt:
        Optional system-role message prepended to the conversation.
    temperature:
        Sampling temperature (default 0.2 — favours focused, factual output).
    top_p:
        Nucleus sampling probability mass (default 0.9).

    Returns the assistant's response text.
    Raises RuntimeError on API or network errors.
    """
    normalized_provider = provider.strip().lower()
    if normalized_provider == "openai_compatible":
        normalized_provider = "openai-compatible"

    resolved_model = _resolve_model(normalized_provider, model)
    resolved_base_url = _resolve_base_url(normalized_provider, base_url)
    resolved_api_key = _get_required_api_key(normalized_provider, api_key)

    if normalized_provider in {"openai", "openai-compatible", "xai"}:
        return _call_openai_compatible(
            provider=normalized_provider,
            prompt=prompt,
            system_prompt=system_prompt,
            model=resolved_model,
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    if normalized_provider == "gemini":
        return _call_gemini(
            prompt=prompt,
            system_prompt=system_prompt,
            model=resolved_model,
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    if normalized_provider == "ollama":
        return _call_ollama(
            prompt=prompt,
            system_prompt=system_prompt,
            model=resolved_model,
            base_url=resolved_base_url,
            temperature=temperature,
            top_p=top_p,
        )

    raise RuntimeError(
        f"Unsupported provider '{provider}'. Use one of: openai-compatible, openai, xai, gemini, ollama."
    )
