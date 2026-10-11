# Instruções para agentes de IA neste repositório

- Este projeto é declaradamente vibecodado. Mantenha o aviso no README e no rodapé da interface.
- **Não cite outros aplicativos ou plataformas de revisão de literatura** (nomes de produtos concorrentes) em código, interface, commits ou documentação. Dependências técnicas (Postgres, Caddy, Ollama etc.) podem ser citadas.
- Documentação e textos de interface em português (pt-BR), com tradução em inglês no i18n. Código e identificadores em inglês.
- Antes de concluir: `ruff check`, `ruff format --check` e `pytest` no backend; `npm run lint`, `npm run typecheck`, `npm test` e `npm run build` no frontend.
- Toda mudança de modelo exige migração Alembic.
- Toda escrita na API usa JSON; não relaxe o middleware `require_json_for_writes`.
