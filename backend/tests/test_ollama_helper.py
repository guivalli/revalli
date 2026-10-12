"""O auxiliar de deploy/ollama-helper: autenticação e ações fixas, sem tocar no systemd."""

import importlib.util
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

HELPER = Path(__file__).resolve().parents[2] / "deploy" / "ollama-helper" / "ollama_helper.py"
TOKEN = "k" * 32


@pytest.fixture
def helper(monkeypatch):
    spec = importlib.util.spec_from_file_location("ollama_helper", HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "TOKEN", TOKEN)
    calls: list[list[str]] = []

    def fake_run(cmd, **_kw):
        calls.append(cmd)
        verb = cmd[1]
        out = {"is-active": "active\n", "is-enabled": "enabled\n"}.get(verb, "")
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    server = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", calls
    server.shutdown()


def test_requires_token(helper):
    url, calls = helper
    assert httpx.get(f"{url}/status").status_code == 401
    assert httpx.post(f"{url}/stop", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert calls == []


def test_status_start_stop_and_nothing_else(helper):
    url, calls = helper
    auth = {"Authorization": f"Bearer {TOKEN}"}
    assert httpx.get(f"{url}/status", headers=auth).json() == {
        "active": True,
        "state": "active",
        "enabled": True,
    }
    assert httpx.post(f"{url}/stop", headers=auth).json()["ok"] is True
    assert ["systemctl", "stop", "ollama"] in calls
    assert httpx.post(f"{url}/start", headers=auth).status_code == 200
    assert ["systemctl", "start", "ollama"] in calls
    n = len(calls)
    # Nenhum outro verbo ou serviço é aceito
    for path in ("/restart", "/disable", "/start;id", "/ssh"):
        assert httpx.post(f"{url}{path}", headers=auth).status_code == 404
    assert len(calls) == n
