"""Cliente mínimo para o protocolo de chat e embeddings compatível com OpenAI.

Ollama, vLLM e a maioria dos provedores remotos aceitam esse formato, então um só cliente
atende tanto a IA local quanto a remota.
"""

import json
import re
from dataclasses import dataclass

import httpx

from revalli.core.config import get_settings

# Permite trocar o transporte nos testes (sem rede)
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


class AIError(Exception):
    """Falha ao falar com o provedor (rede, autenticação ou resposta inválida)."""


@dataclass
class Endpoint:
    base_url: str
    api_key: str
    model: str


@dataclass
class ChatResult:
    content: str
    input_tokens: int
    output_tokens: int


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=get_settings().ai_timeout, transport=_transport)


def _headers(ep: Endpoint) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if ep.api_key:
        h["Authorization"] = f"Bearer {ep.api_key}"
    return h


def _url(ep: Endpoint, path: str) -> str:
    return ep.base_url.rstrip("/") + path


async def _post(ep: Endpoint, path: str, body: dict) -> dict:
    try:
        async with _client() as c:
            r = await c.post(_url(ep, path), json=body, headers=_headers(ep))
    except httpx.HTTPError as exc:
        raise AIError(f"connection: {type(exc).__name__}") from exc
    if r.status_code >= 400:
        # O corpo pode ecoar parte da requisição; guarda só o começo
        raise AIError(f"http {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except ValueError as exc:
        raise AIError("invalid_json_response") from exc


async def chat(ep: Endpoint, messages: list[dict], *, json_mode: bool = True) -> ChatResult:
    body: dict = {"model": ep.model, "messages": messages, "temperature": 0}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = await _post(ep, "/chat/completions", body)
    try:
        content = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("unexpected_response_shape") from exc
    usage = data.get("usage") or {}
    return ChatResult(
        content=content,
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
    )


async def embed(ep: Endpoint, texts: list[str]) -> tuple[list[list[float]], int]:
    data = await _post(ep, "/embeddings", {"model": ep.model, "input": texts})
    try:
        items = sorted(data["data"], key=lambda d: d.get("index", 0))
        vectors = [d["embedding"] for d in items]
    except (KeyError, TypeError) as exc:
        raise AIError("unexpected_response_shape") from exc
    if len(vectors) != len(texts):
        raise AIError("embedding_count_mismatch")
    return vectors, int((data.get("usage") or {}).get("prompt_tokens") or 0)


async def list_models(ep: Endpoint) -> list[str]:
    try:
        async with _client() as c:
            r = await c.get(_url(ep, "/models"), headers=_headers(ep))
    except httpx.HTTPError as exc:
        raise AIError(f"connection: {type(exc).__name__}") from exc
    if r.status_code >= 400:
        raise AIError(f"http {r.status_code}")
    try:
        return sorted(m["id"] for m in r.json().get("data", []))
    except (ValueError, KeyError, TypeError) as exc:
        raise AIError("unexpected_response_shape") from exc


_THINK = re.compile(r"<think>.*?</think>", re.S)


def parse_json(text: str) -> dict:
    """Extrai o objeto JSON da resposta, tolerando blocos de raciocínio e cercas de código."""
    text = _THINK.sub("", text).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise AIError("no_json_in_response") from None
        try:
            value = json.loads(text[start : end + 1])
        except ValueError as exc:
            raise AIError("no_json_in_response") from exc
    if not isinstance(value, dict):
        raise AIError("no_json_in_response")
    return value
