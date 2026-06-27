from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = BACKEND_DIR / ".env"
DEFAULT_SQLITE_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'finance_audit.db').as_posix()}"


class Settings(BaseSettings):
    database_url: str = DEFAULT_SQLITE_DATABASE_URL
    qdrant_url: str = "http://localhost:6333"
    qdrant_local_path: str = "qdrant_local_storage"
    qdrant_collection: str = "accounting_chunks"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "storage/uploads"
    ai_provider: str = "openai-compatible"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_local_model_enabled: bool = True
    ai_fallback_to_rules: bool = True
    embedding_dimension: int = 384
    secret_key: str | None = None
    
    # === LLM 性能参数 ===
    llm_max_concurrent_models: int = 1          # 最大并发模型数（同时运行的LLM数量）
    llm_memory_limit_mb: int = 8192             # 模型内存限制（MB），超过则降级
    llm_preferred_model: str = "qwen2.5-14b"    # 优先使用的模型
    llm_fallback_model: str = "qwen2.5-7b"      # 降级模型（内存不足时）
    llm_timeout_seconds: int = 30               # 单次调用超时（秒）
    
    # === 并行策略 ===
    llm_enable_parallel_parsing: bool = True    # 是否启用双引擎并行解析
    llm_parallel_timeout_seconds: int = 60      # 并行解析总超时（秒）
    
    # === 结果选择策略 ===
    llm_result_selection_mode: str = "auto_best"  # 结果选择模式: auto_best / user_choose / hybrid
    llm_confidence_threshold_auto: float = 0.8    # 自动选择的置信度阈值
    llm_confidence_threshold_user: float = 0.6    # 需要用户确认的置信度阈值
    
    # === 多LLM引擎对比配置 ===
    llm_multi_engine_enabled: bool = True                     # 是否启用多LLM引擎对比
    llm_comparison_mode: str = "parallel_all"                 # 对比模式: parallel_all / sequential_fallback / best_two / custom
    llm_comparison_strategy: str = "weighted_vote"            # 对比策略: weighted_vote / highest_confidence / intersection / union_llm_best / user_review
    llm_comparison_engines: str = "qwen2.5-14b,qwen2.5-7b,deepseek-v2"  # 对比引擎列表（逗号分隔）
    llm_engine_weights: str = '{"qwen2.5-14b":0.40,"qwen2.5-7b":0.25,"deepseek-v2":0.25}'  # 引擎权重（JSON字符串）
    llm_agreement_threshold: float = 0.7                      # 字段一致率阈值（高于此值自动采纳）
    llm_save_all_results: bool = True                         # 是否保存所有LLM结果（用于后续分析）

    model_config = SettingsConfigDict(env_file=BACKEND_ENV_FILE, env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
