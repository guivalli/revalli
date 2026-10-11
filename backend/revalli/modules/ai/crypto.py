"""Cifra das chaves de API. As chaves nunca voltam para a interface depois de salvas."""

import base64
import hashlib
import os
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from revalli.core.config import get_settings


def _secret() -> str:
    s = get_settings()
    if s.secret_key:
        return s.secret_key
    path = Path(s.data_dir) / "secret.key"
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(32)
    # Cria o arquivo só se ainda não existir, para dois processos não gerarem chaves diferentes
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text().strip()
    with os.fdopen(fd, "w") as f:
        f.write(value)
    return value


@lru_cache
def _fernet() -> Fernet:
    key = hashlib.sha256(("revalli-ai-keys:" + _secret()).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # A chave secreta mudou: a chave de API precisa ser cadastrada de novo
        return ""
