from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/greenwashing"
    crawl_concurrency: int = 8
    request_timeout: float = 15.0
    max_pages_per_run: int = 500
    # characters of context captured on each side of a keyword match
    snippet_context: int = 120

    model_config = {"env_file": ".env"}


settings = Settings()
