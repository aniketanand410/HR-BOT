from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str = "hr-policies"
    pinecone_host: str | None = None

    google_drive_root_folder_id: str

    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"

    chunk_size: int = 1800
    chunk_overlap: int = 250
    retrieval_top_k: int = 8
    min_retrieval_score: float = 0.32

    namespace: str = "hr"


@lru_cache
def get_settings() -> Settings:
    return Settings()
