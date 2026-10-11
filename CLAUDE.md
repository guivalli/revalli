# Instruções para agentes de IA neste repositório

- Este projeto é declaradamente vibecodado. Mantenha o aviso no README e no rodapé da interface.
- **Não cite outros aplicativos ou plataformas de revisão de literatura** (nomes de produtos concorrentes) em código, interface, commits ou documentação. Dependências técnicas (Postgres, Caddy, Ollama etc.) podem ser citadas.
- Documentação e textos de interface em português (pt-BR), com tradução em inglês no i18n. Código e identificadores em inglês.
- Antes de concluir: `ruff check`, `ruff format --check` e `pytest` no backend; `npm run lint`, `npm run typecheck`, `npm test` e `npm run build` no frontend.
- Toda mudança de modelo exige migração Alembic.
- Toda escrita na API usa JSON; uploads multipart exigem o cabeçalho `X-Requested-With: ReValli`. Não relaxe o middleware `require_json_for_writes`.
- Tarefas pesadas viram `Job` (ver `modules/records/jobs.py`) e rodam no worker; nos testes rodam inline (`JOBS_INLINE=true`).
- A IA fala só o protocolo de chat compatível com OpenAI (`modules/ai/client.py`). Nos testes, use `client.set_transport(httpx.MockTransport(...))`; nenhum teste deve depender de rede ou de um modelo real.
