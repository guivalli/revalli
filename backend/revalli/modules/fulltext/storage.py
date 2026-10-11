"""Arquivos guardados no volume de dados, nomeados pelo hash do conteúdo."""

import hashlib
import uuid
from pathlib import Path

from revalli.core.config import get_settings


def files_dir(project_id: uuid.UUID) -> Path:
    d = Path(get_settings().data_dir) / "files" / str(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_for(project_id: uuid.UUID, digest: str) -> Path:
    return files_dir(project_id) / f"{digest}.pdf"


def save(project_id: uuid.UUID, data: bytes) -> str:
    digest = sha256(data)
    p = path_for(project_id, digest)
    if not p.exists():
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)
    return digest


def remove_if_unused(project_id: uuid.UUID, digest: str, still_used: bool) -> None:
    if not still_used:
        path_for(project_id, digest).unlink(missing_ok=True)
