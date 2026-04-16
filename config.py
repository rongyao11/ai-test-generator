from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="AI Test Case Generator", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    sqlite_db_url: str = Field(default="sqlite:///./data/app.db", alias="SQLITE_DB_URL")
    retrieval_score_threshold: float = Field(default=0.7, alias="RETRIEVAL_SCORE_THRESHOLD")

    max_upload_size_bytes: int = 10 * 1024 * 1024
    max_retries: int = 3
    raw_chunk_size: int = 800
    raw_chunk_overlap: int = 120

    # AI Provider 选择: "anthropic" 或 "openai" (兼容 MiniMax 等)
    ai_provider: str = Field(default="anthropic", alias="AI_PROVIDER")

    # Anthropic 配置
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")

    # OpenAI 兼容配置（用于 MiniMax 等）
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.minimax.chat/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="abab6.5s-chat", alias="OPENAI_MODEL")

    # API 认证
    api_key: str = Field(default="", alias="API_KEY")

    def ensure_data_dirs(self) -> None:
        Path(self.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        if self.sqlite_db_url.startswith("sqlite:///./"):
            Path(self.sqlite_db_url.removeprefix("sqlite:///./")).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
