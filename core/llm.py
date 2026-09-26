"""
Pluggable LLM layer for the agent.

Snowflake Cortex is the preferred "brain" (keeps AI + data on one platform),
but self-service trial accounts have Cortex disabled. To guarantee the demo
always runs, this module can transparently fall back to a free external LLM
(Groq or Google Gemini). The DATA still lives in and is queried on Snowflake —
only the language-model reasoning moves outside when Cortex is unavailable.

Provider is chosen by LLM_PROVIDER in .env:
    cortex   -> only Snowflake Cortex COMPLETE
    groq     -> only Groq (free, fast, OpenAI-compatible)
    gemini   -> only Google Gemini (free tier)
    auto     -> try Cortex first, fall back to Groq/Gemini if it fails (default)
"""

from __future__ import annotations

import requests
from django.conf import settings

from .snowflake_client import SnowflakeError, cortex_complete


class LLMError(Exception):
    """Raised when no LLM provider can service the request."""


# ---------------------------------------------------------------------------
# External providers
# ---------------------------------------------------------------------------

_GROQ_BASE = "https://api.groq.com/openai/v1"

# Preference order when auto-selecting a Groq chat model. Groq retires models
# often, so we match by substring against whatever the account currently has.
_GROQ_PREFERENCES = [
    "gpt-oss-120b",
    "gpt-oss-20b",
    "llama-3.3-70b",
    "llama-3.1-8b",
    "llama-4",
    "qwen",
]

# Model families that are NOT chat/completion models — skip these.
_GROQ_EXCLUDE = ("whisper", "tts", "guard", "embed", "distil", "prompt-guard")

# Cache the resolved model for the process so we don't list every call.
_groq_model_cache: str | None = None


def _groq_list_models(key: str) -> list[str]:
    resp = requests.get(
        f"{_GROQ_BASE}/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return [m.get("id", "") for m in resp.json().get("data", []) if m.get("id")]


def _groq_pick_model(key: str) -> str:
    """Choose a currently-available Groq chat model."""
    global _groq_model_cache
    if _groq_model_cache:
        return _groq_model_cache

    models = _groq_list_models(key)
    chat = [m for m in models if not any(x in m.lower() for x in _GROQ_EXCLUDE)]

    chosen = ""
    for pref in _GROQ_PREFERENCES:
        match = next((m for m in chat if pref in m.lower()), None)
        if match:
            chosen = match
            break
    if not chosen and chat:
        chosen = chat[0]
    if not chosen:
        raise LLMError("No usable Groq chat model found on this account.")

    _groq_model_cache = chosen
    return chosen


def _groq_call(key: str, model: str, prompt: str):
    return requests.post(
        f"{_GROQ_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=60,
    )


def _groq(prompt: str) -> str:
    key = settings.LLM["GROQ_API_KEY"]
    if not key:
        raise LLMError("GROQ_API_KEY is not set in .env")

    # Use the configured model if set, otherwise auto-detect one that exists.
    model = settings.LLM["GROQ_MODEL"].strip() or _groq_pick_model(key)

    try:
        resp = _groq_call(key, model, prompt)
        # If the configured model is gone (404 / decommissioned), auto-pick and retry.
        if resp.status_code == 404:
            global _groq_model_cache
            _groq_model_cache = None
            model = _groq_pick_model(key)
            resp = _groq_call(key, model, prompt)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.RequestException as exc:
        raise LLMError(f"Groq request failed: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"Unexpected Groq response: {exc}") from exc


def _gemini(prompt: str) -> str:
    key = settings.LLM["GEMINI_API_KEY"]
    if not key:
        raise LLMError("GEMINI_API_KEY is not set in .env")
    model = settings.LLM["GEMINI_MODEL"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    try:
        resp = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.RequestException as exc:
        raise LLMError(f"Gemini request failed: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"Unexpected Gemini response: {exc}") from exc


def _external(prompt: str) -> str:
    """Use whichever external key is configured (Groq preferred)."""
    if settings.LLM["GROQ_API_KEY"]:
        return _groq(prompt)
    if settings.LLM["GEMINI_API_KEY"]:
        return _gemini(prompt)
    raise LLMError(
        "No LLM available: Snowflake Cortex is disabled on this account and no "
        "GROQ_API_KEY / GEMINI_API_KEY is set in .env. Add a free Groq key "
        "(https://console.groq.com/keys) to enable the fallback."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def complete(prompt: str, model: str | None = None) -> str:
    """Return an LLM completion using the configured provider."""
    provider = settings.LLM["PROVIDER"].lower()

    if provider == "groq":
        return _groq(prompt)
    if provider == "gemini":
        return _gemini(prompt)
    if provider == "cortex":
        return cortex_complete(prompt, model)

    # provider == "auto": prefer Cortex, fall back to an external provider.
    try:
        return cortex_complete(prompt, model)
    except SnowflakeError:
        return _external(prompt)


def active_provider() -> str:
    """Best-effort label of which provider will actually be used (for UI)."""
    provider = settings.LLM["PROVIDER"].lower()
    if provider != "auto":
        return provider
    # In auto mode we can't know without calling Cortex; report the fallback
    # that is configured so the UI stays honest.
    if settings.LLM["GROQ_API_KEY"]:
        return "auto (Cortex → Groq)"
    if settings.LLM["GEMINI_API_KEY"]:
        return "auto (Cortex → Gemini)"
    return "auto (Cortex only)"
