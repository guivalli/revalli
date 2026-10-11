import os
import tempfile

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://revalli:revalli@localhost:5432/revalli_test"
)

os.environ["JOBS_INLINE"] = "true"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="revalli-test-")
os.environ["ENRICHMENT_ENABLED"] = "true"
os.environ["API_DELAY_SECONDS"] = "0"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from revalli.core.db import engine  # noqa: E402
from revalli.main import app  # noqa: E402
from revalli.modules.auth.router import login_limiter  # noqa: E402

PASSWORD = "senha-segura-123"


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
async def clean_db():
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, sessions, invitations, projects, project_members, searches,"
                " records, duplicate_groups, not_duplicates, jobs, exclusion_reasons,"
                " decision_events, ai_providers, instance_settings, ai_suggestions, ai_usage,"
                " record_embeddings, record_files, file_pages, studies, study_reports,"
                " extraction_forms, extraction_form_versions, extractions, codes, excerpts,"
                " excerpt_codes, checklist_entries, meta_analyses, grade_rows,"
                " corpus_chunks, corpus_chunk_embeddings, corpus_messages CASCADE"
            )
        )
    login_limiter._hits.clear()


def make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client():
    async with make_client() as c:
        yield c


@pytest.fixture
async def admin(client):
    r = await client.post(
        "/api/setup",
        json={"email": "Admin@Example.org", "full_name": "Admin", "password": PASSWORD},
    )
    assert r.status_code == 201, r.text
    return client


async def invite_and_join(admin_client, email, project_id=None, role=None, name="Pessoa"):
    payload = {"email": email}
    if project_id:
        payload |= {"project_id": str(project_id), "role": role}
    r = await admin_client.post("/api/invitations", json=payload)
    assert r.status_code == 201, r.text
    token = r.json()["invite_url"].rsplit("/", 1)[1]
    c = make_client()
    r = await c.post(
        f"/api/invitations/{token}/accept", json={"full_name": name, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return c
