"""Application configuration loaded from .env and RFP_ environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RFP_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RFP Intelligence"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    data_dir: Path = PROJECT_ROOT / "Assignment-Data-Statements (AI Engineer-Emplay Inc)"
    storage_dir: Path = PROJECT_ROOT / "storage"
    output_dir: Path = PROJECT_ROOT / "outputs"
    log_dir: Path = PROJECT_ROOT / "logs"
    frontend_dist_dir: Path = PROJECT_ROOT / "frontend" / "dist"
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_revision: str = "d4aa6901d3a41ba39fb536a557fa166f842b0e09"
    embedding_cache_dir: Path = PROJECT_ROOT / "storage" / "models"
    embedding_dimensions: int = Field(default=1024, ge=1)
    embedding_batch_size: int = Field(default=4, ge=1)
    embedding_device: str = "cpu"
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    vector_db_dir: Path = PROJECT_ROOT / "storage" / "chroma"
    vector_collection: str = "rfp_chunks_bge_large_1024"
    index_structure_aware: bool = False
    search_mode: Literal["vector", "hybrid"] = "hybrid"
    search_vector_candidates: int = Field(default=20, ge=1, le=100)
    search_keyword_candidates: int = Field(default=20, ge=1, le=100)
    search_vector_weight: float = Field(default=1, gt=0, allow_inf_nan=False)
    search_keyword_weight: float = Field(default=1, gt=0, allow_inf_nan=False)
    search_rerank: bool = False
    search_rerank_candidates: int = Field(default=20, ge=1, le=100)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    reranker_revision: str = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
    reranker_cache_dir: Path = PROJECT_ROOT / "storage" / "models"
    reranker_device: str = "cpu"
    reranker_batch_size: int = Field(default=16, ge=1)
    search_rrf_k: int = Field(default=60, ge=1)
    qa_search_top_k: int = Field(default=5, ge=1, le=20)
    qa_max_followup_queries: int = Field(default=6, ge=1, le=10)
    search_field_keyword_boosts: dict[str, float] = Field(
        default_factory=lambda: {
            "Bid Number": 1.5,
            "Model_no": 1.5,
            "Part_no": 1.5,
            "contact_info": 1.5,
            "Product": 1.5,
        }
    )
    upload_max_files: int = Field(default=200, ge=1)
    upload_max_file_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    upload_max_bytes: int = Field(default=200 * 1024 * 1024, ge=1)
    groq_api_key: SecretStr = SecretStr("")
    llm_model: str = "openai/gpt-oss-120b"
    llm_timeout: float = Field(default=30, gt=0)
    llm_max_tokens: int = Field(default=4096, ge=1)
    llm_tokens_per_minute: int = Field(default=8000, ge=1)
    llm_rate_limit_retries: int = Field(default=2, ge=0, le=5)
    llm_rate_limit_max_wait: float = Field(default=120, gt=0)

    @field_validator("search_field_keyword_boosts")
    @classmethod
    def valid_keyword_boosts(cls, values):
        import math

        if any(not math.isfinite(value) or value <= 0 for value in values.values()):
            raise ValueError("Field keyword boosts must be finite and positive")
        return values

    @field_validator(
        "data_dir",
        "storage_dir",
        "output_dir",
        "log_dir",
        "frontend_dist_dir",
        "embedding_cache_dir",
        "reranker_cache_dir",
        "vector_db_dir",
        mode="after",
    )
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        value = value.expanduser()
        return (value if value.is_absolute() else PROJECT_ROOT / value).resolve()
