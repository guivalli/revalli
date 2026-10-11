"""Servidor MCP (stdio) somente leitura sobre a API do ReValli.

Roda no computador de quem usa o cliente MCP e fala com o ReValli pela API, com uma chave de
leitura criada em "Minha conta". Não acessa o banco nem arquivos do servidor.

    REVALLI_URL=https://revalli.exemplo.org REVALLI_TOKEN=rvl_... python -m revalli.mcp_server

Implementa o mínimo do protocolo (initialize, ping, tools/list, tools/call) em JSON-RPC 2.0,
uma mensagem por linha."""

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

import httpx

from revalli import __version__

PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]
MAX_CHARS = 60_000
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
INSTRUCTIONS = (
    "Dados de revisões de literatura do ReValli, somente leitura. Comece por list_projects. "
    "As respostas valem o que o ReValli tem registrado; decisões de triagem de outros "
    "revisores ficam ocultas enquanto a triagem é cega."
)


@dataclass
class Tool:
    name: str
    description: str
    path: str
    # Parâmetros de caminho, obrigatórios; os de consulta são opcionais
    path_params: tuple[str, ...] = ()
    query: dict[str, str] = field(default_factory=dict)
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def schema(self) -> dict:
        props: dict[str, Any] = {}
        for p in self.path_params:
            props[p] = (
                {"type": "string", "enum": list(self.enums[p])}
                if p in self.enums
                else {"type": "string", "description": "UUID"}
            )
        for q, desc in self.query.items():
            props[q] = {"type": "string", "description": desc}
        return {"type": "object", "properties": props, "required": list(self.path_params)}


PROJECT = ("project_id",)
TOOLS: list[Tool] = [
    Tool("list_projects", "Projetos aos quais a chave dá acesso.", "/api/projects"),
    Tool(
        "project_overview",
        "Contagens do projeto: registros, duplicatas, triagem e texto completo.",
        "/api/projects/{project_id}/summary",
        PROJECT,
    ),
    Tool(
        "prisma_flow",
        "Números do fluxograma PRISMA 2020 do projeto.",
        "/api/projects/{project_id}/report/prisma",
        PROJECT,
    ),
    Tool(
        "list_searches",
        "Buscas registradas: base, estratégia, data e número de registros.",
        "/api/projects/{project_id}/searches",
        PROJECT,
    ),
    Tool(
        "search_records",
        "Referências do projeto, com busca por texto e paginação.",
        "/api/projects/{project_id}/records",
        PROJECT,
        {"q": "texto a buscar", "page": "página (1, 2...)", "page_size": "itens por página"},
    ),
    Tool(
        "get_record",
        "Uma referência completa (título, resumo, autores, identificadores).",
        "/api/projects/{project_id}/records/{record_id}",
        ("project_id", "record_id"),
    ),
    Tool(
        "screening_progress",
        "Progresso da triagem numa fase.",
        "/api/projects/{project_id}/screening/{phase}/progress",
        ("project_id", "phase"),
        enums={"phase": ("title_abstract", "full_text")},
    ),
    Tool(
        "screening_agreement",
        "Concordância entre revisores numa fase.",
        "/api/projects/{project_id}/screening/{phase}/agreement",
        ("project_id", "phase"),
        enums={"phase": ("title_abstract", "full_text")},
    ),
    Tool(
        "list_studies",
        "Estudos incluídos, com os relatórios de cada um.",
        "/api/projects/{project_id}/studies",
        PROJECT,
    ),
    Tool(
        "list_extraction_forms",
        "Formulários de extração e de risco de viés do projeto.",
        "/api/projects/{project_id}/extraction/forms",
        PROJECT,
    ),
    Tool(
        "get_extraction",
        "Dados extraídos de um estudo num formulário (valores, citações, consenso).",
        "/api/projects/{project_id}/extraction/forms/{form_id}/units/{record_id}",
        ("project_id", "form_id", "record_id"),
    ),
    Tool(
        "risk_of_bias",
        "Julgamentos de risco de viés de um formulário.",
        "/api/projects/{project_id}/extraction/forms/{form_id}/rob",
        ("project_id", "form_id"),
    ),
    Tool(
        "list_meta_analyses",
        "Meta-análises do projeto.",
        "/api/projects/{project_id}/meta",
        PROJECT,
    ),
    Tool(
        "meta_analysis_result",
        "Resultado de uma meta-análise: estimativa, heterogeneidade, subgrupos.",
        "/api/projects/{project_id}/meta/{analysis_id}/result",
        ("project_id", "analysis_id"),
    ),
    Tool(
        "grade_summary",
        "Tabela GRADE de sumário de achados.",
        "/api/projects/{project_id}/grade",
        PROJECT,
    ),
    Tool(
        "coding_matrix",
        "Matriz de códigos qualitativos por estudo.",
        "/api/projects/{project_id}/coding/matrix",
        PROJECT,
    ),
]
BY_NAME = {t.name: t for t in TOOLS}


class ToolError(Exception):
    """Falha de uso da ferramenta; volta como resultado com isError, não como erro de protocolo."""


class InvalidParams(Exception):
    pass


class Server:
    def __init__(
        self, base_url: str, token: str, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": f"revalli-mcp/{__version__}",
            },
            timeout=60,
            transport=transport,
        )

    async def close(self) -> None:
        await self.http.aclose()

    # --- ferramentas -----------------------------------------------------------

    async def call_tool(self, name: str, args: dict) -> str:
        tool = BY_NAME.get(name)
        if tool is None:
            raise InvalidParams(f"Unknown tool: {name}")
        values: dict[str, str] = {}
        for p in tool.path_params:
            v = args.get(p)
            if not isinstance(v, str) or not v:
                raise InvalidParams(f"Missing argument: {p}")
            if p in tool.enums:
                if v not in tool.enums[p]:
                    raise InvalidParams(f"{p} must be one of {', '.join(tool.enums[p])}")
            elif not UUID.match(v):
                raise InvalidParams(f"{p} must be a UUID")
            values[p] = v
        params = {q: str(args[q]) for q in tool.query if args.get(q) not in (None, "")}
        try:
            resp = await self.http.get(tool.path.format(**values), params=params)
        except httpx.HTTPError as exc:
            raise ToolError(f"Could not reach ReValli: {type(exc).__name__}") from exc
        if resp.status_code == 401:
            raise ToolError("The API key is invalid, revoked or expired.")
        if resp.status_code in (403, 404):
            raise ToolError("Not found, or the key has no access to it.")
        if resp.status_code >= 400:
            raise ToolError(f"ReValli answered HTTP {resp.status_code}.")
        text = json.dumps(resp.json(), ensure_ascii=False, indent=1)
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n… (truncated; use filters or pagination)"
        return text

    # --- protocolo -------------------------------------------------------------

    async def handle(self, msg: dict) -> dict | None:
        """Responde a uma mensagem JSON-RPC; notificações (sem id) não têm resposta."""
        mid = msg.get("id")
        method = msg.get("method")
        if mid is None:
            return None
        if not isinstance(method, str):
            return _error(mid, -32600, "Invalid request")
        params = msg.get("params") or {}
        try:
            if method == "initialize":
                wanted = params.get("protocolVersion")
                version = wanted if wanted in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
                return _result(
                    mid,
                    {
                        "protocolVersion": version,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "revalli", "version": __version__},
                        "instructions": INSTRUCTIONS,
                    },
                )
            if method == "ping":
                return _result(mid, {})
            if method == "tools/list":
                tools = [
                    {"name": t.name, "description": t.description, "inputSchema": t.schema()}
                    for t in TOOLS
                ]
                return _result(mid, {"tools": tools})
            if method == "tools/call":
                try:
                    text = await self.call_tool(
                        params.get("name", ""), params.get("arguments") or {}
                    )
                except ToolError as exc:
                    return _result(
                        mid, {"content": [{"type": "text", "text": str(exc)}], "isError": True}
                    )
                return _result(mid, {"content": [{"type": "text", "text": text}], "isError": False})
        except InvalidParams as exc:
            return _error(mid, -32602, str(exc))
        return _error(mid, -32601, f"Method not found: {method}")


def _result(mid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


async def serve(server: Server, stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, stdin.readline)
        if not line:
            return
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = _error(None, -32700, "Parse error")
        else:
            reply = await server.handle(msg) if isinstance(msg, dict) else None
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


def main() -> int:
    url = os.environ.get("REVALLI_URL", "").strip()
    token = os.environ.get("REVALLI_TOKEN", "").strip()
    if not url or not token:
        print("Defina REVALLI_URL e REVALLI_TOKEN.", file=sys.stderr)
        return 2

    async def run() -> None:
        server = Server(url, token)
        try:
            await serve(server)
        finally:
            await server.close()

    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
