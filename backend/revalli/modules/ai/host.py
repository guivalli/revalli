"""Liga e desliga o Ollama do computador por meio do auxiliar em `deploy/ollama-helper`."""

import httpx

from revalli.core.config import get_settings

_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


class HelperError(Exception):
    """O auxiliar não respondeu como esperado."""


def configured() -> bool:
    s = get_settings()
    return bool(s.ollama_helper_url and s.ollama_helper_token)


async def call(method: str, path: str) -> dict:
    s = get_settings()
    url = s.ollama_helper_url.rstrip("/") + path
    headers = {"Authorization": f"Bearer {s.ollama_helper_token}"}
    try:
        async with httpx.AsyncClient(timeout=70, transport=_transport) as http:
            r = await http.request(method, url, headers=headers)
    except httpx.HTTPError as exc:
        raise HelperError("unreachable") from exc
    if r.status_code != 200:
        raise HelperError("rejected")
    try:
        return r.json()
    except ValueError as exc:
        raise HelperError("bad_response") from exc
