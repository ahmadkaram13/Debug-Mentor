"""
Thin abstraction over two possible LLM backends:
  - OpenAI (e.g. gpt-4o) via the official `openai` SDK
  - A local model served by Ollama (e.g. llama3) via its HTTP API

Selected with the LLM_PROVIDER env var: "openai" (default) or "ollama".
"""
import json
import os
import time
from typing import Dict, Iterator, List

import requests


class LLMError(RuntimeError):
    pass


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "openai").lower()


def _openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o")


def _ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "llama3")


def _ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


# Number of tokens Ollama is allowed to generate per response (mirrors OpenAI's limit).
_OLLAMA_NUM_PREDICT = 500

# Retry settings for transient Ollama connection errors.
_OLLAMA_MAX_RETRIES = 2
_OLLAMA_RETRY_DELAY = 1.5  # seconds


def _call_openai(messages: List[Dict[str, str]]) -> str:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError("The 'openai' package is not installed. Run: pip install openai") from e

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("OPENAI_API_KEY is not set in the environment.")

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=_openai_model(),
            messages=messages,
            temperature=0.4,
            max_tokens=500,
        )
    except Exception as e:  # noqa: BLE001 - surface any SDK error as LLMError
        raise LLMError(f"OpenAI API call failed: {e}") from e

    return response.choices[0].message.content


def _call_ollama(messages: List[Dict[str, str]]) -> str:
    host = _ollama_host()
    model = _ollama_model()
    last_exc: Exception | None = None

    for attempt in range(1 + _OLLAMA_MAX_RETRIES):
        if attempt > 0:
            time.sleep(_OLLAMA_RETRY_DELAY)
        try:
            resp = requests.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_predict": _OLLAMA_NUM_PREDICT},
                },
                timeout=120,
            )
            resp.raise_for_status()
        except requests.ConnectionError as e:
            last_exc = e
            continue  # retry on connection errors
        except requests.RequestException as e:
            raise LLMError(
                f"Could not reach Ollama at {host}. Is `ollama serve` running "
                f"and have you pulled the model with `ollama pull {model}`? ({e})"
            ) from e

        data = resp.json()
        message = data.get("message", {})
        content = message.get("content")
        if not content:
            raise LLMError(f"Unexpected response shape from Ollama: {data}")
        return content

    raise LLMError(
        f"Could not reach Ollama at {host} after {1 + _OLLAMA_MAX_RETRIES} attempts. "
        f"Is `ollama serve` running? ({last_exc})"
    )


def get_completion(messages: List[Dict[str, str]]) -> str:
    """messages: list of {"role": "system"|"user"|"assistant", "content": str}"""
    provider = _provider()
    if provider == "ollama":
        return _call_ollama(messages)
    if provider == "openai":
        return _call_openai(messages)
    raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use 'openai' or 'ollama'.")


# --- Streaming variants ------------------------------------------------------

def _stream_openai(messages: List[Dict[str, str]]) -> Iterator[str]:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError("The 'openai' package is not installed. Run: pip install openai") from e

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("OPENAI_API_KEY is not set in the environment.")

    client = OpenAI(api_key=api_key)
    try:
        stream = client.chat.completions.create(
            model=_openai_model(),
            messages=messages,
            temperature=0.4,
            max_tokens=500,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:  # noqa: BLE001
        raise LLMError(f"OpenAI streaming call failed: {e}") from e


def _stream_ollama(messages: List[Dict[str, str]]) -> Iterator[str]:
    host = _ollama_host()
    model = _ollama_model()
    last_exc: Exception | None = None

    for attempt in range(1 + _OLLAMA_MAX_RETRIES):
        if attempt > 0:
            time.sleep(_OLLAMA_RETRY_DELAY)
        try:
            resp = requests.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {"num_predict": _OLLAMA_NUM_PREDICT},
                },
                timeout=120,
                stream=True,
            )
            resp.raise_for_status()
        except requests.ConnectionError as e:
            last_exc = e
            continue  # retry on connection errors
        except requests.RequestException as e:
            raise LLMError(
                f"Could not reach Ollama at {host}. Is `ollama serve` running "
                f"and have you pulled the model with `ollama pull {model}`? ({e})"
            ) from e

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = data.get("message", {}).get("content", "")
            if content:
                yield content
            if data.get("done"):
                return  # success — stop retry loop

    raise LLMError(
        f"Could not reach Ollama at {host} after {1 + _OLLAMA_MAX_RETRIES} attempts. "
        f"Is `ollama serve` running? ({last_exc})"
    )


def get_completion_stream(messages: List[Dict[str, str]]) -> Iterator[str]:
    """Yields text deltas as they arrive from the model."""
    provider = _provider()
    if provider == "ollama":
        yield from _stream_ollama(messages)
    elif provider == "openai":
        yield from _stream_openai(messages)
    else:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use 'openai' or 'ollama'.")
