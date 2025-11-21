from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from functools import lru_cache

class Settings(BaseSettings):
    ENV: str = "dev"

    # --- X OAuth ---
    X_CLIENT_ID: str
    X_CLIENT_SECRET: str
    X_REDIRECT_URI: AnyUrl
    X_SCOPES: str = "tweet.read users.read offline.access"

    # --- Token encryption ---
    FERNET_KEY: str

    # --- Database ---
    # Default to SQLite for local dev, but Render will provide PostgreSQL URL via env var
    DATABASE_URL: str = "sqlite:///./ngodb.sqlite3"

    class Config:
        env_file = ".env"
        extra = "ignore"

    # --- IbtikarAI ---
    IBTIKAR_URL: str | None = None
    HF_TOKEN: str | None = None  # Optional Hugging Face API token


@lru_cache(maxsize=1)
def get_settings() -> "Settings":
    return Settings()

settings = get_settings()
