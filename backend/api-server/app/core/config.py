from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "nexusclaw-api"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    AUTH_TOKEN_EXPIRE_HOURS: int = 12
    AUTH_SEED_ADMIN_USERNAME: str = "admin"
    AUTH_SEED_ADMIN_PASSWORD: str = "admin123456"
    AUTH_SEED_ADMIN_NICKNAME: str = "平台管理员"

    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_DB: str = "nexusclaw"

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    FILE_STORAGE_ROOT: str = "storage/uploads"
    SCENE_TEMPLATE_ROOT: str = "storage/scene_templates"
    SCENE_IR1249_TEMPLATE_URL: str = "https://www.ird.gov.hk/eng/pdf/ir1249.pdf"
    SCENE_IRC3111A_TEMPLATE_URL: str = "https://www.ird.gov.hk/eng/pdf/irc3111a_normal.pdf"
    FILE_PDF_MIN_TEXT_CHARS_FOR_NATIVE: int = 120
    FILE_PDF_PARSE_MODE: str = "ocr_first"
    FILE_PREVIEW_MAX_CHARS: int = 20000
    FILE_TABLE_EXTRACTION_ENABLED: bool = True
    FILE_TABLE_EXTRACTION_MAX_PAGES: int = 8
    FILE_TABLE_EXTRACTION_MIN_PAGE_SCORE: int = 4
    FILE_TABLE_EXTRACTION_TIMEOUT_SECONDS: int = 120
    FILE_TABLE_VALIDATION_SAMPLE_SIZE: int = 5
    PADDLE_OCR_BACKEND: str = "auto"
    PADDLE_OCR_PARSE_URL: str | None = None
    PADDLE_OCR_API_KEY: str | None = None
    PADDLE_OCR_TIMEOUT_SECONDS: int = 180
    PADDLE_OCR_LOCAL_PYTHON_BIN: str = ".venv-paddleocr/bin/python"
    PADDLE_OCR_LOCAL_SCRIPT_PATH: str = "app/scripts/local_paddle_ocr_runner.py"
    PADDLE_OCR_LOCAL_DET_MODEL_DIR: str | None = "~/.paddlex/official_models/PP-OCRv5_server_det"
    PADDLE_OCR_LOCAL_REC_MODEL_DIR: str | None = "~/.paddlex/official_models/PP-OCRv5_server_rec"
    PADDLE_OCR_LOCAL_LANG: str = "ch"

    ELASTICSEARCH_URL: str | None = None
    ELASTICSEARCH_USERNAME: str | None = None
    ELASTICSEARCH_PASSWORD: str | None = None
    ELASTICSEARCH_INDEX: str = "nexusclaw_knowledge"
    ELASTICSEARCH_TIMEOUT_SECONDS: int = 10

    VECTOR_SEARCH_URL: str | None = None
    VECTOR_UPSERT_URL: str | None = None
    VECTOR_DELETE_URL: str | None = None
    VECTOR_TIMEOUT_SECONDS: int = 20

    RERANK_URL: str | None = None
    RERANK_TIMEOUT_SECONDS: int = 20
    RERANK_PROTECT_RAW_TOP1: bool = True
    RERANK_PROTECT_MIN_SCORE: float = 0.6
    RERANK_PROTECT_MIN_MARGIN: float = 0.08
    RERANK_PROTECT_SCORE_EPSILON: float = 1e-4

    LOCAL_RAG_DB_PATH: str = "storage/local_rag/local_rag.sqlite3"
    LOCAL_RAG_TIMEOUT_SECONDS: int = 60
    LOCAL_RAG_EMBEDDING_PROVIDER: str = "hash"
    LOCAL_RAG_EMBEDDING_URL: str | None = None
    LOCAL_RAG_EMBEDDING_MODEL: str | None = None
    LOCAL_RAG_EMBEDDING_MODEL_PATH: str | None = None
    LOCAL_RAG_EMBEDDING_API_KEY: str | None = None
    LOCAL_RAG_EMBEDDING_DIMENSION: int = 64
    LOCAL_RAG_EMBEDDING_DEVICE: str = "auto"
    LOCAL_RAG_EMBEDDING_BATCH_SIZE: int = 16
    LOCAL_RAG_RERANK_PROVIDER: str = "embedding_cosine"
    LOCAL_RAG_RERANK_MODEL: str = "BAAI/bge-reranker-base"
    LOCAL_RAG_RERANK_MODEL_PATH: str | None = None
    LOCAL_RAG_RERANK_DEVICE: str = "auto"
    LOCAL_RAG_RERANK_BATCH_SIZE: int = 8
    LOCAL_RAG_RERANK_UPSTREAM_URL: str | None = None
    LOCAL_RAG_RERANK_UPSTREAM_API_KEY: str | None = None
    LOCAL_RAG_RERANK_UPSTREAM_MODEL: str | None = None
    LOCAL_RAG_TORCH_NUM_THREADS: int = 1
    LOCAL_RAG_ALLOW_DEGRADED_FALLBACK: bool = True
    LOCAL_RAG_PRELOAD_MODELS: bool = False

    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_FUSION_TOP_K: int = 10
    RETRIEVAL_MIN_SCORE: float = 0.2
    RETRIEVAL_REFUSAL_MIN_SCORE: float = 0.35
    RETRIEVAL_REFUSAL_MIN_MARGIN: float = 0.05
    USE_CHUNK_RETRIEVAL: bool = False
    CHUNK_RETRIEVAL_TOP_K: int = 6
    CHUNK_RERANK_TOP_K: int = 8
    FILE_QA_ALLOWED_AS_SOLO_EVIDENCE: bool = False
    ENABLE_HARD_SCOPE_REFUSAL: bool = True
    OFFICIAL_CONTACT_EMAIL: str = ""

    DEEPSEEK_API_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_CHAT_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT_SECONDS: int = 60
    DEEPSEEK_MAX_HISTORY_TURNS: int = 6
    DEEPSEEK_ENABLE_QUERY_REWRITE: bool = True
    DEEPSEEK_ENABLE_RETRIEVAL_GUARD: bool = True
    DEEPSEEK_ENABLE_SCENE_CARRYOVER_INTENT: bool = True
    DEEPSEEK_SCENE_CARRYOVER_TIMEOUT_SECONDS: int = 8
    SCENE_CARRYOVER_MIN_CONFIDENCE: float = 0.72
    SCENE_CARRYOVER_FALLBACK_TO_RULES: bool = True

    ADDRESS_RESOLVER_ENABLE_ALS: bool = True
    ADDRESS_RESOLVER_ENABLE_LANDSD: bool = False
    ALS_BASE_URL: str = "https://www.als.gov.hk"
    ALS_TIMEOUT_SECONDS: int = 8
    ALS_RESULT_LIMIT: int = 5

    SCENE_MAIL_DELIVERY_MODE: str = "draft_only"
    SCENE_CONFIRMATION_SECRET: str = "local-scene-confirmation-secret"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True

    CORS_ORIGINS: list[str] = ["*"]

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def ensure_storage_root() -> Path:
    storage_root = Path(settings.FILE_STORAGE_ROOT)
    storage_root.mkdir(parents=True, exist_ok=True)
    return storage_root
