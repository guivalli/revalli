from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://revalli:revalli@localhost:5432/revalli"
    redis_url: str = "redis://localhost:6379/0"

    # Endereço público usado para montar links de convite (ex.: https://revalli.exemplo.org)
    public_url: str = "http://localhost:8080"
    # Marque como true quando o acesso for por HTTPS
    cookie_secure: bool = False
    session_days: int = 14
    invite_days: int = 7

    login_max_attempts: int = 10
    login_window_seconds: int = 300

    # Roda tarefas de fundo na própria requisição (testes e depuração)
    jobs_inline: bool = False
    max_import_mb: int = 50
    max_pdf_mb: int = 100
    max_zip_mb: int = 2000

    # Enriquecimento de metadados pela API pública do OpenAlex
    enrichment_enabled: bool = True
    enrichment_contact_email: str = ""
    openalex_url: str = "https://api.openalex.org"

    # Busca direta nas bases (PubMed, OpenAlex, Europe PMC) e snowballing de citações
    search_apis_enabled: bool = True
    pubmed_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    europepmc_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    # Opcional: aumenta o limite do PubMed de 3 para 10 requisições por segundo
    ncbi_api_key: str = ""
    # Máximo de registros trazidos por uma busca ou por um snowballing
    api_search_max: int = 10_000
    # Pausa entre requisições, para respeitar o limite das APIs públicas
    api_delay_seconds: float = 0.35

    # Chave usada para cifrar as chaves de API dos provedores de IA. Se ficar vazia,
    # o ReValli gera uma e guarda em data_dir/secret.key na primeira vez.
    secret_key: str = ""
    data_dir: str = "/data"
    # Tempo máximo de uma chamada a um modelo de IA, em segundos
    ai_timeout: int = 120
    # Quanto texto do PDF vai para a IA na extração (~4 caracteres por token)
    ai_extract_max_chars: int = 40_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
