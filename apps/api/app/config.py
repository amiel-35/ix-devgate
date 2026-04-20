from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+psycopg://devgate:devgate@localhost:5432/devgate"

    SESSION_SECRET_KEY: str = "changeme"
    SESSION_TTL_DAYS: int = 7

    EMAIL_PROVIDER: str = "resend"
    RESEND_API_KEY: str = ""

    # Cloudflare — jamais exposé vers le frontend
    CF_API_TOKEN: str = ""
    CF_ACCOUNT_ID: str = ""


settings = Settings()
