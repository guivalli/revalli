# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Instruções para agentes de IA neste repositório

ReValli: ferramenta auto-hospedada de revisão de literatura (importação, deduplicação, triagem cega, IA, extração, síntese, relatório). Backend FastAPI + SQLAlchemy async + Celery; frontend React + TypeScript + Vite.

## Regras do projeto

- Este projeto é declaradamente vibecodado. Mantenha o aviso no README e no rodapé da interface.
- **Não cite outros aplicativos ou plataformas de revisão de literatura** (nomes de produtos concorrentes) em código, interface, commits ou documentação. Dependências técnicas (Postgres, Caddy, Ollama etc.) podem ser citadas.
- Documentação e textos de interface em português (pt-BR), com tradução em inglês no i18n. Código e identificadores em inglês.
- Antes de concluir: `ruff check`, `ruff format --check` e `pytest` no backend; `npm run lint`, `npm run typecheck`, `npm test` e `npm run build` no frontend.
- Toda mudança de modelo exige migração Alembic.
- Toda escrita na API usa JSON; uploads multipart exigem o cabeçalho `X-Requested-With: ReValli`. Não relaxe o middleware `require_json_for_writes`.
- Tarefas pesadas viram `Job` (ver `modules/records/jobs.py`) e rodam no worker; nos testes rodam inline (`JOBS_INLINE=true`).
- A IA fala só o protocolo de chat compatível com OpenAI (`modules/ai/client.py`). Nos testes, use `client.set_transport(httpx.MockTransport(...))`; nenhum teste deve depender de rede ou de um modelo real.

## Comandos

Backend (`backend/`, ambiente em `.venv`; os testes precisam do Postgres de desenvolvimento com o banco `revalli_test`):

```bash
docker compose -f deploy/docker-compose.dev.yml up -d   # Postgres + Redis (com podman: podman start revalli-dev-db revalli-dev-redis)
cd backend && . .venv/bin/activate
pytest                                   # tudo
pytest tests/test_ai.py::test_nome -q    # um teste
ruff check . && ruff format --check .    # ruff format . aplica
alembic upgrade head                     # nova migração: alembic revision --autogenerate -m "..."
uvicorn revalli.main:app --reload        # docs em /api/docs
```

Frontend (`frontend/`): `npm run dev` (proxy de `/api` para :8000), `npm test`, `npx vitest run src/caminho/arquivo.test.ts`, `npm run lint` (oxlint), `npm run typecheck`, `npm run build`.

Stack de produção local (a partir da raiz; nesta máquina é Podman com `podman-compose`, não Docker; roda em `http://localhost:1515`, via `HTTP_PORT` e `PUBLIC_URL` em `deploy/.env`):

```bash
podman-compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
# Só `--build` NÃO recria contêineres já criados com outra imagem. Depois de reconstruir:
podman-compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --force-recreate --no-deps api worker scheduler web
```

`deploy/.env` é local e ignorado pelo git (inclui chaves). Variável nova de ambiente precisa entrar em `x-backend-env` no `docker-compose.yml` e, se for opção, em `deploy/.env.example`.

Depois de mudar código, reconstrua e recrie `api worker scheduler web` (o frontend só muda com `web`). Um job em andamento morre junto com o worker: espere terminar antes de recriar.

## Arquitetura

**Backend em módulos verticais.** Cada `revalli/modules/<área>/` tem `router.py`, `schemas.py`, `models.py`, `service.py` e, quando há trabalho em segundo plano, `tasks.py`. `main.py` registra os routers; `revalli/models.py` importa todos os modelos (o Alembic só enxerga o que passa por ali). Permissões vêm de `core/deps.py` (`current_user`, `get_membership`, `require_lead`; papéis lead, reviewer, arbitrator, extractor, observer).

**Configurações em JSONB.** `Project.settings` guarda blocos soltos: o protocolo da triagem (`ScreeningSettings`: critérios, critérios detalhados, vocabulário de etiquetas, destaque de termos) na raiz e as opções de IA do projeto na chave `"ai"`. A configuração da instalação fica em `InstanceSetting`: chave `ai` (provedores, modelo por tarefa) e chave `sources` (chave do OpenAlex cifrada; `modules/sources/keys.py`). A chave salva na interface vale mais que `OPENALEX_API_KEY`. O valor fica em memória por processo: quem consulta o OpenAlex chama `keys.load(db)` no começo (busca, snowballing, revisão viva); os testes zeram com `keys.reset()` no `conftest`. A rota `PUT /screening/settings` grava o objeto inteiro: quem edita parte dele deve partir do que está salvo.

**Jobs.** `create_job` → `dispatch` → Celery `run_job` → `execute` (reivindica o job de forma atômica, roda o handler registrado com `@handler("tipo")`, grava `result`). Filas `gpu` (provedor local), `remote` e `default`. Um handler que retorna `{"stopped": "user"}` termina como `cancelled`; o botão Parar só muda o status para `cancelling` e o handler `ai_screen` relê esse status entre registros (ver `CANCELLABLE` em `records/router.py`).

**IA.** `modules/ai/client.py` é o único cliente (chat e embeddings compatíveis com OpenAI). `resolve(db, "screening", local_only)` escolhe provedor e modelo; as tarefas auxiliares (organizar critérios, etiquetas, motivos, tradução e assistente de busca) usam o modelo de `screening`. As respostas da triagem são cache em `AISuggestion`, chaveado por `(registro, fase, modelo, hash do prompt)`: mudar critérios, vocabulário ou instruções invalida o cache de propósito. Os prompts ficam em inglês em `ai/prompts.py`; o idioma da resposta vem da variável `language`. `modules/ai/protocol.py` concentra o que ajuda a montar o protocolo (critérios, etiquetas, motivos de exclusão). **A triagem por IA só vale em título e resumo**: o prompt não recebe o PDF, a interface esconde o botão no texto completo e `estimate`/`run` respondem 409 `ai_phase_not_supported`. Triar o texto completo (PDF principal truncado em `AI_EXTRACT_MAX_CHARS`) é uma decisão adiada. O Ollama do computador liga e desliga pela tela IA: `deploy/ollama-helper/` (script do computador, instalado pelo usuário com `install.sh`, que pede `sudo`), `modules/ai/host.py` e as rotas `GET/POST /ai/local/ollama` (só admin; sem `OLLAMA_HELPER_URL`/`TOKEN` o cartão some). O assistente de busca guarda a conversa por pessoa e projeto (`search_assistant_chats`, últimas 28 mensagens).

**Busca em bases.** `modules/sources/clients.py` fala com PubMed, OpenAlex e Europe PMC; SciELO e PePSIC são buscas no OpenAlex restritas às revistas da coleção (lista via ArticleMeta). O OpenAlex impõe regras que o cliente trata: curinga exige `search.exact`, frases com curinga são reescritas, consultas com mais de 5 operadores têm 1 requisição por segundo, e sem `OPENALEX_API_KEY` o orçamento diário é pequeno. LILACS/BVS e Portal CAPES não têm busca direta (bloqueio anti-robô, chave ou sem API): só importação por arquivo e tradução da estratégia. Não contorne desafios anti-robô.

**Texto completo.** `fulltext/service.find_open_access` percorre, por registro sem PDF: OpenAlex (em lote), Unpaywall (exige `ENRICHMENT_CONTACT_EMAIL`), Europe PMC e a página do artigo (`finders.article_page`, lê `citation_pdf_url`; também usa as páginas que o OpenAlex conhece e ignora `openalex.org`). Todo download passa por `core/safefetch.py` (sem rede interna, tenta o próximo IP se um não conecta, confere `%PDF`). Roda 4 registros em paralelo, com o banco serial. O que ninguém achou aparece em `GET /files/pending` (e `.csv`) com DOI e link. O acesso pelo proxy da instituição (CAFe) foi tentado e removido em 2026-10-12: o link pelo proxy não abriu o artigo (404 e página inicial do Portal) e o proxy não atende `doi.org`. Fica para depois; se voltar, não há login automático na CAFe nem download em lote pelo proxy, de propósito. Nenhuma fonte pirata.

**Frontend.** `src/api/*.ts` tem um arquivo de hooks do TanStack Query por módulo do backend; `src/pages/project/*` são as abas do projeto (rotas em `App.tsx`, abas em `ProjectLayout.tsx`, dados do projeto via `useProjectContext`). Textos em `src/i18n/pt-BR.json` e `en.json`, e um teste exige as mesmas chaves nos dois. Mensagens de erro da API chegam como `código` ou `código: detalhe` e são traduzidas por `errors.<código>`. Tema claro, escuro ou automático pela classe `dark` na raiz (`lib/theme.ts`; o variante `dark:` do Tailwind foi trocado para seguir a classe). As cores da marca (azul e verde-limão do logo) e os neutros frios estão em `index.css`; os logos com fundo transparente, nas versões clara e escura, em `public/brand` (componente `Logo`). Navegação em pílulas (`components/pills.ts`), menu lateral (`AppMenu`) e gavetas (`Drawer`, `CriteriaDrawer`) mudam de tela sem trocar de rota; a lista de abas do projeto vem de `pages/project/tabs.ts`.

## Armadilhas

- `tests/conftest.py` limpa as tabelas com um `TRUNCATE` explícito: tabela nova precisa entrar na lista.
- Requisições de escrita sem corpo JSON levam 415; em testes e hooks use `json={}`.
- O fake de LLM em `tests/test_ai.py` decide a resposta pelo início do prompt de sistema; prompts novos devem ser distintos o bastante, e o ramo mais específico vem primeiro.
- Os testes de fontes usam `API_DELAY_SECONDS=0`, o que desliga esperas e retentativas com pausa; teste esse comportamento com `monkeypatch` do delay e de `asyncio.sleep`.
- Migrações são numeradas à mão (`0016_...`), com `revision`/`down_revision` encadeados.
- Tarefas do worker abrem uma engine própria (`NullPool`, um loop por tarefa): nunca use `SessionLocal` nem estado global ligado a loop dentro de um handler; use o `db` recebido.
- Handler longo que só atualiza `job.progress` não grava nada até o próximo `commit`: faça `commit` ao atualizar o andamento.
- Testes que trocam o `httpx.AsyncClient` do serviço de PDFs devem tratar todos os hosts que a cadeia consulta (OpenAlex, Unpaywall, Europe PMC, `doi.org`, páginas); um host sem resposta quebra o teste.
- Exportação RIS da BVS: o resumo vem em dois idiomas (todos os `AB` são juntados), `TT` é o título traduzido e entra na deduplicação, `MH` vira palavra-chave só sem `KW`. O campo `TI` pode estar em inglês num artigo em português.
