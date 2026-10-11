"""Download de URLs que não são do próprio ReValli, sem alcançar a rede interna (SSRF).

O nome é resolvido aqui, o endereço é conferido e a conexão vai para esse mesmo IP (com o nome
original no cabeçalho Host e no SNI do TLS), o que fecha a troca de DNS entre a conferência e a
conexão. Cada redirecionamento passa pela mesma conferência. Credenciais só seguem para o
servidor original."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from revalli.core.config import get_settings

MAX_REDIRECTS = 3
Resolver = Callable[[str, int], Awaitable[list[str]]]


class FetchError(Exception):
    """O código (blocked_address, http_404, too_large...) vira o detalhe mostrado à pessoa."""


@dataclass
class Fetched:
    url: str
    data: bytes
    content_type: str


async def _system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchError("dns_failed") from exc
    return sorted({str(i[4][0]) for i in infos})


_resolver: Resolver = _system_resolver


def set_resolver(resolver: Resolver | None) -> None:
    """Troca o resolvedor (nos testes, para não depender de DNS)."""
    global _resolver
    _resolver = resolver or _system_resolver


def ip_allowed(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


async def public_ips(host: str, port: int) -> list[str]:
    allow_private = get_settings().feed_allow_private
    try:
        literal = ipaddress.ip_address(host)
        ips = [str(literal)]
    except ValueError:
        lowered = host.lower()
        internal = (
            lowered == "localhost"
            or lowered.endswith((".localhost", ".local", ".internal"))
            or "." not in lowered  # nomes de serviços da rede de contêineres ("db", "redis")
        )
        if internal and not allow_private:
            raise FetchError("blocked_address") from None
        ips = await _resolver(host, port)
    if not ips:
        raise FetchError("dns_failed")
    if not allow_private and not all(ip_allowed(ip) for ip in ips):
        raise FetchError("blocked_address")
    return ips


def _pin(parts, ip: str) -> str:
    host = f"[{ip}]" if ":" in ip else ip
    netloc = f"{host}:{parts.port}" if parts.port else host
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


async def get_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int,
    headers: dict[str, str] | None = None,
    secret_headers: dict[str, str] | None = None,
    read_timeout: float = 60,
) -> Fetched:
    origin = urlsplit(url).hostname
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise FetchError("invalid_url")
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == "https" else 80)
        ips = await public_ips(host, port)
        request_headers = {**(headers or {}), "Host": parts.netloc.split("@")[-1]}
        if secret_headers and host == origin:
            request_headers.update(secret_headers)
        try:
            async with client.stream(
                "GET",
                _pin(parts, ips[0]),
                headers=request_headers,
                extensions={"sni_hostname": host},
                timeout=read_timeout,
            ) as resp:
                if resp.is_redirect and resp.headers.get("location"):
                    url = urljoin(url, resp.headers["location"])
                    continue
                if resp.status_code != 200:
                    raise FetchError(f"http_{resp.status_code}")
                size, chunks = 0, []
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchError("too_large")
                    chunks.append(chunk)
                return Fetched(url, b"".join(chunks), resp.headers.get("content-type", ""))
        except httpx.HTTPError as exc:
            raise FetchError(f"connection: {type(exc).__name__}") from exc
    raise FetchError("too_many_redirects")
