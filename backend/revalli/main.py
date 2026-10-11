from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from revalli import __version__
from revalli.core.db import SessionLocal
from revalli.modules.ai.router import project_router as ai_project_router
from revalli.modules.ai.router import router as ai_router
from revalli.modules.auth.router import router as auth_router
from revalli.modules.corpus.router import router as corpus_router
from revalli.modules.extraction.router import router as extraction_router
from revalli.modules.fulltext.router import router as fulltext_router
from revalli.modules.meta.router import router as meta_router
from revalli.modules.projects.router import router as projects_router
from revalli.modules.records.router import router as records_router
from revalli.modules.reports.router import router as reports_router
from revalli.modules.screening.router import router as screening_router
from revalli.modules.sources.router import router as sources_router
from revalli.modules.synthesis.router import router as synthesis_router
from revalli.modules.tokens.router import router as tokens_router

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

app = FastAPI(
    title="ReValli API",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.middleware("http")
async def require_json_for_writes(request: Request, call_next):
    """Proteção contra CSRF: formulários de outros sites não conseguem enviar JSON
    sem passar pelo preflight de CORS, que esta API não libera."""
    if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/"):
        content_type = request.headers.get("content-type", "")
        has_body = request.headers.get("content-length", "0") not in ("", "0")
        # Uploads (multipart) precisam de um cabeçalho próprio, que também força o preflight
        is_upload = content_type.startswith("multipart/form-data") and (
            request.headers.get("x-requested-with") == "ReValli"
        )
        if (
            (has_body or request.method != "DELETE")
            and not content_type.startswith("application/json")
            and not is_upload
        ):
            return JSONResponse({"detail": "json_required"}, status_code=415)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


@app.get("/api/health")
async def health():
    db_ok = True
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return JSONResponse(
        {"status": "ok" if db_ok else "degraded", "database": db_ok, "version": __version__},
        status_code=200 if db_ok else 503,
    )


app.include_router(auth_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(records_router, prefix="/api")
app.include_router(screening_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(ai_project_router, prefix="/api")
app.include_router(fulltext_router, prefix="/api")
app.include_router(extraction_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(synthesis_router, prefix="/api")
app.include_router(meta_router, prefix="/api")
app.include_router(corpus_router, prefix="/api")
app.include_router(tokens_router, prefix="/api")
