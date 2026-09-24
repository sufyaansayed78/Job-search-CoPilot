from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Core
    SECRET_KEY: str = "job-search-copilot-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/jobcopilot"

    # Celery / Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # LLM
    ANTHROPIC_API_KEY: str = ""
    # Haiku is deliberate here, not a placeholder: gap analysis is a background
    # batch job, not an interactive chat, so we optimise for cost/throughput
    # over the extra reasoning depth a larger model would give us.
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"

    class Config:
        env_file = ".env"


settings = Settings()
