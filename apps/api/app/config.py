from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+psycopg://devgate:devgate@localhost:5432/devgate"

    SESSION_SECRET_KEY: str = "changeme"
    SESSION_TTL_DAYS: int = 7

    COOKIE_SECURE: bool = True

    EMAIL_PROVIDER: str = "fake"  # fake | smtp | resend
    RESEND_API_KEY: str = ""

    # SMTP (dev : mailpit, prod : Brevo / Mailgun / Amazon SES…)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "DevGate <no-reply@devgate.local>"
    SMTP_USER: str = ""      # Brevo : login SMTP (email du compte)
    SMTP_PASSWORD: str = ""  # Brevo : clé API SMTP

    # Frontend URL (pour construire les magic links)
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # CORS — origines autorisées (surcharger en production)
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Cloudflare — jamais exposé vers le frontend
    CF_API_TOKEN: str = ""
    CF_ACCOUNT_ID: str = ""
    CF_ZONE_ID: str = ""   # Zone DNS pour les routes hostname

    # Secret store — master key de chiffrement (obligatoire en production)
    DEVGATE_MASTER_KEY: str = ""


settings = Settings()
