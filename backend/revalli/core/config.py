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
    # Permite que fontes externas (URLs de atualização) apontem para a rede interna
    feed_allow_private: bool = False
    # Pausa entre requisições, para respeitar o limite das APIs públicas
    api_delay_seconds: float = 0.35

    # Login único (OpenID Connect). Fica ligado quando issuer, client_id e client_secret existem.
    # O endereço de retorno a cadastrar no provedor é PUBLIC_URL + /api/auth/oidc/callback
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_scopes: str = "openid email profile"
    oidc_button_label: str = ""
    # Cria a conta de quem entra pela primeira vez (sem permissão de administração)
    oidc_auto_create: bool = False
    # Domínios de e-mail aceitos, separados por vírgula; vazio aceita qualquer um
    oidc_allowed_domains: str = ""
    # Exige que o provedor declare o e-mail como verificado (desligue só se ele não envia o campo)
    oidc_require_verified_email: bool = True

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
