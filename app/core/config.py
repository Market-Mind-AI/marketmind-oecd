from urllib.parse import quote

from pydantic_settings import BaseSettings

from app.db.ssl_config import sslmode_query_suffix


class Settings(BaseSettings):
    app_name: str = "marketmind-oecd"
    app_env: str = "local"
    app_version: str = "0.1.0"

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "marketmind_oecd"
    database_user: str = "marketmind"
    database_password: str = "marketmind_password"

    # TLS for the Postgres connection. "disable" keeps local docker-compose
    # working unchanged; Azure Database for PostgreSQL Flexible Server needs at
    # least "require" because it refuses plaintext connections
    # (`require_secure_transport = ON`). See app/db/ssl_config.py.
    database_ssl_mode: str = "disable"

    oecd_base_url: str = "https://sdmx.oecd.org/public/rest/v1"
    # Os três números abaixo são os mesmos nos coletores que falam HTTP (World
    # Bank, OCDE, UN Data); tentativas e espera valem também para o Google Ads.
    # 60s era o valor do UN Data, o maior dos três; ficou o de todos, porque
    # encurtar só troca uma resposta lenta por uma tentativa a mais. Quando e
    # quanto esperar entre tentativas está em app/utils/retry.py.
    default_timeout: int = 60
    default_retries: int = 5
    default_backoff: int = 2

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.database_user}:{quote(self.database_password, safe='')}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def database_url_sync(self) -> str:
        # Alembic runs through psycopg2, which reads `sslmode` straight off
        # the DSN. The async engine cannot — it gets an SSLContext instead,
        # built from the same setting in app/db/ssl_config.py.
        return (
            f"postgresql://{self.database_user}:{quote(self.database_password, safe='')}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
            f"{sslmode_query_suffix(self.database_ssl_mode)}"
        )


settings = Settings()
