import io
import json
import re
import uuid

import pytest
from httpx import ASGITransport

from revalli.main import app
from revalli.mcp_server import BY_NAME, TOOLS, Server, serve


def _server(token: str) -> Server:
    return Server("http://test", token, transport=ASGITransport(app=app))


async def _rpc(server: Server, method: str, params: dict | None = None, mid: int = 1):
    return await server.handle(
        {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}
    )


async def _token(admin, **body) -> str:
    r = await admin.post("/api/tokens", json={"name": "mcp", **body})
    return r.json()["token"]


async def test_initialize_list_and_call(admin):
    pid = (await admin.post("/api/projects", json={"title": "Revisão MCP"})).json()["id"]
    server = _server(await _token(admin))
    try:
        init = await _rpc(server, "initialize", {"protocolVersion": "2024-11-05"})
        assert init["result"]["protocolVersion"] == "2024-11-05"
        assert init["result"]["capabilities"] == {"tools": {}}
        # Versão desconhecida: responde com a mais nova que o servidor entende
        init = await _rpc(server, "initialize", {"protocolVersion": "1999-01-01"})
        assert init["result"]["protocolVersion"] == "2025-06-18"
        assert (
            await server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        )
        assert (await _rpc(server, "ping"))["result"] == {}

        listed = (await _rpc(server, "tools/list"))["result"]["tools"]
        assert {t["name"] for t in listed} == {t.name for t in TOOLS}
        assert all(t["inputSchema"]["type"] == "object" for t in listed)

        called = await _rpc(server, "tools/call", {"name": "list_projects", "arguments": {}})
        assert called["result"]["isError"] is False
        projects = json.loads(called["result"]["content"][0]["text"])
        assert [p["id"] for p in projects] == [pid]

        called = await _rpc(
            server, "tools/call", {"name": "project_overview", "arguments": {"project_id": pid}}
        )
        assert called["result"]["isError"] is False
        assert "records_total" in called["result"]["content"][0]["text"]
        called = await _rpc(
            server,
            "tools/call",
            {"name": "search_records", "arguments": {"project_id": pid, "q": "x"}},
        )
        assert called["result"]["isError"] is False
    finally:
        await server.close()


async def test_errors_are_reported_without_leaking(admin):
    pid = (await admin.post("/api/projects", json={"title": "A"})).json()["id"]
    server = _server(await _token(admin))
    try:
        r = await _rpc(server, "tools/call", {"name": "nope", "arguments": {}})
        assert r["error"]["code"] == -32602
        r = await _rpc(
            server, "tools/call", {"name": "get_record", "arguments": {"project_id": pid}}
        )
        assert r["error"]["code"] == -32602 and "record_id" in r["error"]["message"]
        # Não deixa montar outro caminho por um "id"
        r = await _rpc(
            server,
            "tools/call",
            {"name": "project_overview", "arguments": {"project_id": "../ai/providers"}},
        )
        assert r["error"]["code"] == -32602
        r = await _rpc(
            server,
            "tools/call",
            {"name": "screening_progress", "arguments": {"project_id": pid, "phase": "x"}},
        )
        assert r["error"]["code"] == -32602
        # Projeto que não existe: erro da ferramenta, não do protocolo
        r = await _rpc(
            server,
            "tools/call",
            {"name": "project_overview", "arguments": {"project_id": str(uuid.uuid4())}},
        )
        assert r["result"]["isError"] is True
        assert (await _rpc(server, "resources/list"))["error"]["code"] == -32601
    finally:
        await server.close()

    bad = _server("rvl_wrong")
    try:
        r = await _rpc(bad, "tools/call", {"name": "list_projects", "arguments": {}})
        assert r["result"]["isError"] is True and "invalid" in r["result"]["content"][0]["text"]
    finally:
        await bad.close()


async def test_project_scoped_key_in_mcp(admin):
    a = (await admin.post("/api/projects", json={"title": "A"})).json()["id"]
    b = (await admin.post("/api/projects", json={"title": "B"})).json()["id"]
    server = _server(await _token(admin, project_id=a))
    try:
        r = await _rpc(server, "tools/call", {"name": "list_projects", "arguments": {}})
        assert [p["id"] for p in json.loads(r["result"]["content"][0]["text"])] == [a]
        r = await _rpc(
            server, "tools/call", {"name": "project_overview", "arguments": {"project_id": b}}
        )
        assert r["result"]["isError"] is True
    finally:
        await server.close()


async def test_stdio_loop(admin):
    server = _server(await _token(admin))
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    stdin = io.StringIO("\n".join(json.dumps(m) for m in lines) + "\n\nnot json\n")
    stdout = io.StringIO()
    try:
        await serve(server, stdin, stdout)
    finally:
        await server.close()
    replies = [json.loads(x) for x in stdout.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, 2, None]
    assert replies[2]["error"]["code"] == -32700
    assert replies[0]["result"]["serverInfo"]["name"] == "revalli"


def test_tool_names_are_unique_and_paths_resolve():
    assert len(BY_NAME) == len(TOOLS)
    for t in TOOLS:
        assert set(re.findall(r"{(\w+)}", t.path)) == set(t.path_params)


@pytest.mark.parametrize("name", [t.name for t in TOOLS])
def test_every_tool_is_a_get_route_that_exists(name):
    spec = app.openapi()
    tool = BY_NAME[name]
    template = re.sub(r"{(\w+)}", lambda m: "{" + m.group(1) + "}", tool.path)
    assert "get" in spec["paths"][template], template
