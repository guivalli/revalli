"""Chave do OpenAlex: a salva pela interface (cifrada, na instalação) vale mais que a do ambiente.

O valor fica em memória no processo. Quem vai consultar o OpenAlex chama `load(db)` antes, o
que serve para a API e para o worker (cada tarefa do worker abre a própria conexão).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from revalli.core.config import get_settings
from revalli.modules.ai.crypto import decrypt, encrypt
from revalli.modules.ai.models import InstanceSetting

KEY = "sources"
_stored: str | None = None


def reset() -> None:
    global _stored
    _stored = None


async def stored(db: AsyncSession) -> str:
    row = await db.get(InstanceSetting, KEY)
    encrypted = ((row.value if row else None) or {}).get("openalex_api_key_enc", "")
    return decrypt(encrypted) if encrypted else ""


async def load(db: AsyncSession) -> None:
    global _stored
    _stored = await stored(db)


def openalex_key() -> str:
    return _stored or get_settings().openalex_api_key


def source() -> str:
    if _stored:
        return "ui"
    return "env" if get_settings().openalex_api_key else "none"


async def save(db: AsyncSession, value: str) -> None:
    """Grava a chave (vazio apaga) e atualiza o valor deste processo."""
    global _stored
    row = await db.get(InstanceSetting, KEY)
    data = dict((row.value if row else None) or {})
    if value:
        data["openalex_api_key_enc"] = encrypt(value)
    else:
        data.pop("openalex_api_key_enc", None)
    if row is None:
        db.add(InstanceSetting(key=KEY, value=data))
    else:
        row.value = data
    _stored = value


async def institution_proxy(db: AsyncSession) -> str:
    row = await db.get(InstanceSetting, KEY)
    return str(((row.value if row else None) or {}).get("institution_proxy", ""))


async def save_institution_proxy(db: AsyncSession, template: str) -> None:
    row = await db.get(InstanceSetting, KEY)
    data = dict((row.value if row else None) or {})
    if template:
        data["institution_proxy"] = template
    else:
        data.pop("institution_proxy", None)
    if row is None:
        db.add(InstanceSetting(key=KEY, value=data))
    else:
        row.value = data


def hint(value: str) -> str:
    return f"…{value[-4:]}" if value else ""
