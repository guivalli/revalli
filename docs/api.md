# API pública e servidor MCP

> Este projeto é vibecodado: o código e esta documentação foram escritos com auxílio intensivo de IA. Revise antes de confiar nos resultados.

A API do ReValli é a mesma que a interface usa. A documentação interativa fica em `/api/docs`. Para scripts e para ferramentas externas, existem **chaves de API somente leitura**.

## Chaves

Em **Minha conta** (clique no seu nome, no topo), crie uma chave com:
- um nome, para você reconhecê-la;
- o projeto a que ela dá acesso (ou todos os seus projetos);
- uma validade opcional, em dias.

O valor completo (`rvl_…`) aparece **uma única vez**. O servidor guarda só um hash, então uma chave perdida não se recupera: revogue e crie outra.

### O que uma chave faz e não faz

- **Só lê.** Qualquer pedido que não seja `GET` ou `HEAD` recebe `403 token_read_only`.
- **Só nas rotas de projetos** (`/api/projects/...`) e em `/api/auth/me`. Administração da instalação, provedores de IA e a gestão de chaves ficam de fora (`403 token_scope`). Uma chave não cria outra.
- **Age como você.** Ela enxerga o que você enxerga, com o mesmo cegamento: em triagem cega, as decisões dos outros revisores não aparecem.
- **Uma chave por projeto** é o jeito de dar o mínimo: com `project_id`, os outros projetos respondem `404`.
- Revogar ou deixar vencer corta o acesso na hora. Desativar o usuário também.

### Exemplo

```bash
curl -H "Authorization: Bearer rvl_..." https://revalli.exemplo.org/api/projects
curl -H "Authorization: Bearer rvl_..." \
  "https://revalli.exemplo.org/api/projects/<id>/records?q=metformin&page=1"
```

Com o cabeçalho `Authorization` presente, só a chave vale; o cookie de sessão é ignorado. Trate a chave como uma senha: quem a tem lê o que você lê.

## Servidor MCP

O servidor MCP deixa um cliente MCP (um assistente de IA, por exemplo) consultar seus projetos por ferramentas de leitura. Ele roda **no seu computador**, fala com o ReValli pela API e usa a chave; não acessa o banco.

```bash
cd backend && pip install -e .
REVALLI_URL=https://revalli.exemplo.org REVALLI_TOKEN=rvl_... python -m revalli.mcp_server
```

Configuração típica de um cliente MCP (formato `mcpServers`):

```json
{
  "mcpServers": {
    "revalli": {
      "command": "python",
      "args": ["-m", "revalli.mcp_server"],
      "env": {
        "REVALLI_URL": "https://revalli.exemplo.org",
        "REVALLI_TOKEN": "rvl_..."
      }
    }
  }
}
```

### Ferramentas

| Ferramenta | O que devolve |
|---|---|
| `list_projects` | projetos acessíveis pela chave |
| `project_overview` | contagens do projeto |
| `prisma_flow` | números do fluxograma PRISMA 2020 |
| `list_searches` | buscas registradas, com a estratégia |
| `search_records` | referências, com busca por texto e paginação |
| `get_record` | uma referência completa |
| `screening_progress`, `screening_agreement` | progresso e concordância da triagem, por fase |
| `list_studies` | estudos incluídos e seus relatórios |
| `list_extraction_forms`, `get_extraction`, `risk_of_bias` | formulários, dados extraídos e risco de viés |
| `list_meta_analyses`, `meta_analysis_result` | meta-análises e seus resultados |
| `grade_summary` | tabela GRADE |
| `coding_matrix` | matriz de códigos qualitativos |

Respostas longas são cortadas em cerca de 60 mil caracteres; use os filtros e a paginação.

### Decisões e limites

- O servidor implementa à mão o mínimo do protocolo (`initialize`, `ping`, `tools/list`, `tools/call`) por stdio, sem depender de um SDK. Ele não oferece `resources` nem `prompts`.
- Não há ferramenta de escrita nem a de conversa com os PDFs: a chave é só de leitura. Perguntar aos PDFs custa tokens de IA, então fica na interface.
- Os dados que o assistente lê passam pelo provedor desse assistente. Num projeto com texto sensível, use uma chave limitada ao projeto e confira o que o seu cliente MCP envia para fora.
