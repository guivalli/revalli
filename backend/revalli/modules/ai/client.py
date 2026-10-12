"""Cliente mínimo para o protocolo de chat e embeddings compatível com OpenAI.

Ollama, vLLM e a maioria dos provedores remotos aceitam esse formato, então um só cliente
atende tanto a IA local quanto a remota.
"""

import asyncio
import json
import re
import time
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
    # Pedidos por minuto que o provedor aceita (faixas gratuitas); None = sem limite
    rpm: int | None = None


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


# Próximo instante livre por provedor (relógio monótono). Só guarda números; não depende do
# loop de eventos, então vale para as várias tarefas do mesmo processo.
_next_slot: dict[str, float] = {}

# Faixas gratuitas respondem 429 tanto no teto por minuto (basta esperar) quanto na cota do dia
# (esperar não adianta). O corpo costuma dizer qual foi.
_DAILY = re.compile(r"per.?day|daily|\bTPD\b|\bRPD\b|per.?month|quota exceeded", re.IGNORECASE)
MAX_RETRIES = 4


def reset_throttle() -> None:
    _next_slot.clear()


async def _throttle(ep: Endpoint) -> None:
    """Espaça os pedidos para não passar de `ep.rpm` por minuto."""
    if not ep.rpm or get_settings().api_delay_seconds <= 0:
        return
    interval = 60.0 / ep.rpm
    now = time.monotonic()
    slot = max(_next_slot.get(ep.base_url, 0.0), now)
    _next_slot[ep.base_url] = slot + interval
    if slot > now:
        await asyncio.sleep(slot - now)


def _retry_wait(r: httpx.Response, attempt: int) -> float:
    try:
        header = float(r.headers.get("retry-after", ""))
    except ValueError:
        header = 0.0
    return min(max(header, 2.0 * 2**attempt), 60.0)


async def _post(ep: Endpoint, path: str, body: dict) -> dict:
    sleeps = get_settings().api_delay_seconds > 0
    for attempt in range(MAX_RETRIES + 1):
        await _throttle(ep)
        try:
            async with _client() as c:
                r = await c.post(_url(ep, path), json=body, headers=_headers(ep))
        except httpx.HTTPError as exc:
            raise AIError(f"connection: {type(exc).__name__}") from exc
        if r.status_code == 429 or r.status_code == 503:
            if r.status_code == 429 and _DAILY.search(r.text):
                raise AIError("quota_exhausted")
            if attempt < MAX_RETRIES:
                if sleeps:
                    await asyncio.sleep(_retry_wait(r, attempt))
                continue
            raise AIError("rate_limited")
        if r.status_code >= 400:
            # O corpo pode ecoar parte da requisição; guarda só o começo
            raise AIError(f"http {r.status_code}: {r.text[:300]}")
        try:
            return r.json()
        except ValueError as exc:
            raise AIError("invalid_json_response") from exc
    raise AIError("rate_limited")


async def chat(ep: Endpoint, messages: list[dict], *, json_mode: bool = True) -> ChatResult:
    body: dict = {"model": ep.model, "messages": messages, "temperature": 0}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        data = await _post(ep, "/chat/completions", body)
    except AIError as exc:
        # Alguns provedores não aceitam o modo JSON; os prompts já pedem JSON de qualquer forma
        text = str(exc)
        if not (json_mode and text.startswith("http 400") and "response_format" in text):
            raise
        del body["response_format"]
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
    try:
        data = await _post(ep, "/embeddings", {"model": ep.model, "input": texts})
    except AIError as exc:
        # Modelos de chat (ex.: qwen2.5 no Ollama) recusam embeddings com 501
        if str(exc).startswith("http 501") or "support embeddings" in str(exc):
            raise AIError("embeddings_unsupported") from exc
        raise
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
