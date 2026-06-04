class SREAgentError(Exception):
    """Base exception for all SRE Agent errors."""
    pass


class KubernetesClientError(SREAgentError):
    """Failed to interact with Kubernetes cluster."""
    pass


class LokiQueryError(SREAgentError):
    """Failed to query Loki logs."""
    pass


class PrometheusQueryError(SREAgentError):
    """Failed to query Prometheus metrics."""
    pass


class TracingQueryError(SREAgentError):
    """Failed to query Traces (Jaeger)."""
    pass


class LLMError(SREAgentError):
    """Failed to query LLM or parse its output."""
    pass


class LLMClientError(LLMError):
    """Specific error calling the LLM client API."""
    pass


class RemediationError(SREAgentError):
    """Failed to perform remediation actions."""
    pass


class OrchestratorError(SREAgentError):
    """Errors within the Orchestrator loop."""
    pass


class IncidentMemoryError(SREAgentError):
    """Failed to store or retrieve incident memory."""
    pass


class RunbookError(SREAgentError):
    """Failed to parse or retrieve runbooks."""
    pass


class VectorStoreError(SREAgentError):
    """Failed to perform operations on the vector store."""
    pass