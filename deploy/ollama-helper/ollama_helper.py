#!/usr/bin/env python3
"""Auxiliar que deixa o ReValli ligar e desligar o Ollama deste computador.

Roda no computador (fora dos contêineres), só com a biblioteca padrão. Aceita
três pedidos, todos com o cabeçalho `Authorization: Bearer <token>`:

    GET  /status   estado do serviço
    POST /start    liga o serviço `ollama`
    POST /stop     desliga o serviço `ollama`

Não executa mais nada: o nome do serviço é fixo e não vem do pedido.
"""

import hmac
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UNIT = os.environ.get("OLLAMA_HELPER_UNIT", "ollama")
TOKEN = os.environ.get("OLLAMA_HELPER_TOKEN", "")
ACTIONS = {"start", "stop"}


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", *args, UNIT], capture_output=True, text=True, timeout=60, check=False
    )


def status() -> dict:
    active = _systemctl("is-active").stdout.strip()
    enabled = _systemctl("is-enabled").stdout.strip()
    return {"active": active == "active", "state": active or "unknown", "enabled": enabled == "enabled"}


def act(action: str) -> dict:
    if action not in ACTIONS:
        raise ValueError(action)
    done = _systemctl(action)
    result = status()
    result["ok"] = done.returncode == 0
    if done.returncode != 0:
        result["error"] = (done.stderr or done.stdout).strip()[:300]
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "revalli-ollama-helper"

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self) -> bool:
        sent = self.headers.get("Authorization", "")
        expected = f"Bearer {TOKEN}"
        return bool(TOKEN) and hmac.compare_digest(sent.encode(), expected.encode())

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        if self.path != "/status":
            return self._send(404, {"error": "not_found"})
        self._send(200, status())

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            return self._send(401, {"error": "unauthorized"})
        action = self.path.lstrip("/")
        if action not in ACTIONS:
            return self._send(404, {"error": "not_found"})
        self._send(200, act(action))

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    if len(TOKEN) < 24:
        sys.exit("Defina OLLAMA_HELPER_TOKEN com pelo menos 24 caracteres.")
    host = os.environ.get("OLLAMA_HELPER_BIND", "0.0.0.0")
    port = int(os.environ.get("OLLAMA_HELPER_PORT", "11435"))
    print(f"ollama-helper em {host}:{port} (serviço: {UNIT})", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
