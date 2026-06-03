from enum import Enum


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    DETECTING = "detecting"
    INVESTIGATING = "investigating"
    RCA_IN_PROGRESS = "rca_in_progress"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"


class RootCauseCategory(str, Enum):
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CRASHLOOP = "crashloop"
    IMAGE_PULL = "image_pull"
    NODE_FAILURE = "node_failure"
    NETWORK_ISSUE = "network_issue"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_FAILURE = "dependency_failure"
    MEMORY_LEAK = "memory_leak"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationAction(str, Enum):
    RESTART_POD = "restart_pod"
    SCALE_DEPLOYMENT = "scale_deployment"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    DELETE_POD = "delete_pod"
    CORDON_NODE = "cordon_node"
    DRAIN_NODE = "drain_node"
    UPDATE_CONFIG = "update_config"
    PATCH_DEPLOYMENT = "patch_deployment"
    NO_ACTION = "no_action"


class AgentType(str, Enum):
    METRIC = "metric_agent"
    LOG = "log_agent"
    TRACE = "trace_agent"
    KUBERNETES = "kubernetes_agent"
    CONSENSUS = "consensus_agent"
    REASONING = "reasoning_agent"
    RISK = "risk_agent"
    VERIFICATION = "verification_agent"


# Prometheus query templates
PROM_QUERIES = {
    "cpu_usage": 'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{pod}.*"}}[5m])) by (pod)',
    "memory_usage": 'sum(container_memory_working_set_bytes{{namespace="{namespace}",pod=~"{pod}.*"}}) by (pod)',
    "error_rate": 'sum(rate(http_requests_total{{namespace="{namespace}",status=~"5.."}}[5m])) / sum(rate(http_requests_total{{namespace="{namespace}"}}[5m]))',
    "restart_count": 'sum(kube_pod_container_status_restarts_total{{namespace="{namespace}",pod=~"{pod}.*"}}) by (pod)',
    "pod_ready": 'kube_pod_status_ready{{namespace="{namespace}",pod=~"{pod}.*"}}',
    "latency_p99": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{namespace="{namespace}"}}[5m])) by (le))',
    "node_cpu": "1 - avg(rate(node_cpu_seconds_total{mode='idle'}[5m])) by (node)",
    "node_memory": "1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)",
}

# Loki log query templates
LOKI_QUERIES = {
    "error_logs": '{{namespace="{namespace}",pod=~"{pod}.*"}} |= "error" | json',
    "oom_logs": '{{namespace="{namespace}"}} |= "OOMKilled"',
    "crashloop_logs": '{{namespace="{namespace}",pod=~"{pod}.*"}} |= "CrashLoopBackOff"',
    "image_pull_logs": '{{namespace="{namespace}"}} |= "ImagePullBackOff"',
    "recent_logs": '{{namespace="{namespace}",pod=~"{pod}.*"}}',
}

# Confidence thresholds
CONFIDENCE_HIGH = 0.85
CONFIDENCE_MEDIUM = 0.65
CONFIDENCE_LOW = 0.40

# Timeouts (seconds)
AGENT_TIMEOUT = 60
ORCHESTRATOR_TIMEOUT = 300
REMEDIATION_TIMEOUT = 120
VERIFICATION_TIMEOUT = 60

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2.0