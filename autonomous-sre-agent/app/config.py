from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # LLM
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    llm_model: str = Field("gemini-2.5-flash", env="LLM_MODEL")
    llm_max_tokens: int = Field(4096, env="LLM_MAX_TOKENS")
    llm_temperature: float = Field(0.1, env="LLM_TEMPERATURE")

    # Prometheus
    prometheus_url: str = Field("http://localhost:9090", env="PROMETHEUS_URL")
    prometheus_timeout: int = Field(30, env="PROMETHEUS_TIMEOUT")

    # Loki
    loki_url: str = Field("http://localhost:3100", env="LOKI_URL")
    loki_timeout: int = Field(30, env="LOKI_TIMEOUT")

    # Jaeger
    jaeger_url: str = Field("http://localhost:16686", env="JAEGER_URL")
    tracing_timeout: int = Field(30, env="TRACING_TIMEOUT")

    # Kubernetes
    kubeconfig_path: str = Field("/root/.kube/config", env="KUBECONFIG_PATH")
    k8s_in_cluster: bool = Field(False, env="K8S_IN_CLUSTER")
    k8s_namespace: str = Field("default", env="K8S_NAMESPACE")

    # Vector Store
    chroma_persist_dir: str = Field("./data/embeddings", env="CHROMA_PERSIST_DIR")
    embedding_model: str = Field("all-MiniLM-L6-v2", env="EMBEDDING_MODEL")

    # Runbooks
    runbooks_dir: str = Field("./data/runbooks", env="RUNBOOKS_DIR")

    # Application
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    environment: str = Field("development", env="ENVIRONMENT")

    # Remediation Safety
    auto_remediate: bool = Field(False, env="AUTO_REMEDIATE")
    dry_run: bool = Field(True, env="DRY_RUN")
    remediation_confidence_threshold: float = Field(0.85, env="REMEDIATION_CONFIDENCE_THRESHOLD")
    risk_threshold: Literal["low", "medium", "high"] = Field("medium", env="RISK_THRESHOLD")

    # Anomaly Detection
    anomaly_contamination: float = Field(0.05, env="ANOMALY_CONTAMINATION")
    threshold_cpu_percent: float = Field(85.0, env="THRESHOLD_CPU_PERCENT")
    threshold_memory_percent: float = Field(90.0, env="THRESHOLD_MEMORY_PERCENT")
    threshold_error_rate: float = Field(0.05, env="THRESHOLD_ERROR_RATE")
    threshold_latency_p99_ms: float = Field(2000.0, env="THRESHOLD_LATENCY_P99_MS")

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache()
def get_settings() -> Settings:
    return Settings()