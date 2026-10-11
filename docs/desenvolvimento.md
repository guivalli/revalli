# Desenvolvimento

> Projeto vibecodado: boa parte do código é gerada com assistentes de IA. Toda mudança passa pela CI (lint, testes e build) antes de entrar na `main`.

## Estrutura

```
backend/    API (FastAPI), modelos (SQLAlchemy), migrações (Alembic), worker (Celery)
frontend/   Interface (React + TypeScript + Vite + Tailwind), servida pelo Caddy
deploy/     Docker Compose de produção e de desenvolvimento
docs/       Documentação
```

## Backend

```bash
docker compose -f deploy/docker-compose.dev.yml up -d   # Postgres e Redis locais
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn revalli.main:app --reload
pytest
ruff check . && ruff format --check .
# Atualizações automáticas (opcional): um único processo
celery -A revalli.workers.celery_app beat --loglevel=info
```

A documentação interativa da API fica em `http://localhost:8000/api/docs`.

Nova migração: `alembic revision --autogenerate -m "descrição"`.

## Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, com /api redirecionado para :8000
npm test
npm run lint && npm run typecheck
```

## Convenções

- Código e identificadores em inglês; textos da interface via i18n (`frontend/src/i18n/*.json`), sempre em pt-BR e en.
- Toda escrita na API usa JSON (proteção contra CSRF).
- Toda mudança de banco tem migração Alembic.
- Não citar produtos ou serviços de terceiros na interface ou na documentação, exceto dependências técnicas.
