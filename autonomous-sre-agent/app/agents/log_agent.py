from typing import Any
from app.constants import RootCauseCategory, AgentType
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LogAgent:
    def __init__(self):
        self.agent_type = AgentType.LOG

    async def analyze(self, logs: dict[str, list[str]]) -> dict[str, Any]:
        """
        Analyze Loki logs to identify patterns and determine the root cause.
        """
        logger.info("log_agent_analysis_start")

        category = RootCauseCategory.UNKNOWN
        description = "No anomalous patterns or errors found in logs."
        confidence = 0.0
        evidence = []

        oom_logs = logs.get("oom", [])
        crashloop_logs = logs.get("crashloop", [])
        image_pull_logs = logs.get("image_pull", [])
        error_logs = logs.get("errors", [])
        recent_logs = logs.get("recent", [])

        # 1. Check for OOM
        if oom_logs or any("oomkilled" in line.lower() or "out of memory" in line.lower() for line in error_logs + recent_logs):
            category = RootCauseCategory.MEMORY_LEAK
            description = "OOMKilled log pattern detected. The container was killed for exceeding memory limits."
            confidence = 0.95
            evidence.append("Found OOMKilled pattern in logs")
            if oom_logs:
                evidence.append(f"OOM log sample: {oom_logs[0][:150]}")

        # 2. Check for Image Pull Failures
        elif image_pull_logs or any("imagepullbackoff" in line.lower() or "errimagepull" in line.lower() for line in error_logs + recent_logs):
            category = RootCauseCategory.IMAGE_PULL
            description = "Image pull failure detected. Kubernetes cannot pull the requested container image."
            confidence = 0.95
            evidence.append("Found ImagePullBackOff or ErrImagePull in logs")

        # 3. Check for Crash Loop
        elif crashloop_logs or any("crashloopbackoff" in line.lower() or "back-off restarting failed container" in line.lower() for line in error_logs + recent_logs):
            category = RootCauseCategory.CRASHLOOP
            description = "CrashLoopBackOff logs found. The application container is repeatedly failing and restarting."
            confidence = 0.95
            evidence.append("Found CrashLoopBackOff pattern in logs")

        # 4. Check general error logs for patterns
        else:
            # Let's inspect errors
            network_keywords = ["connection refused", "timeout", "network unreachable", "dial tcp", "host unresolved"]
            dependency_keywords = ["database connection failed", "db connection error", "service unavailable", "dependency failed", "http 502", "http 503", "http 504"]
            config_keywords = ["invalid config", "configuration error", "missing environment variable", "access denied", "authentication failed", "invalid credentials"]

            net_count = 0
            dep_count = 0
            cfg_count = 0
            total_errors = len(error_logs)

            for line in error_logs:
                line_lower = line.lower()
                if any(kw in line_lower for kw in network_keywords):
                    net_count += 1
                if any(kw in line_lower for kw in dependency_keywords):
                    dep_count += 1
                if any(kw in line_lower for kw in config_keywords):
                    cfg_count += 1

            if dep_count > 0 and dep_count >= net_count and dep_count >= cfg_count:
                category = RootCauseCategory.DEPENDENCY_FAILURE
                description = "Logs indicate a downstream service or database dependency failure."
                confidence = 0.85
                evidence.append(f"Found {dep_count} dependency failure patterns in error logs.")
            elif net_count > 0 and net_count >= cfg_count:
                category = RootCauseCategory.NETWORK_ISSUE
                description = "Logs indicate connection timeouts or network reachability issues."
                confidence = 0.80
                evidence.append(f"Found {net_count} network error patterns in logs.")
            elif cfg_count > 0:
                category = RootCauseCategory.CONFIG_ERROR
                description = "Logs indicate configuration or credential mismatches."
                confidence = 0.85
                evidence.append(f"Found {cfg_count} config error patterns in logs.")
            elif total_errors > 10:
                category = RootCauseCategory.CRASHLOOP
                description = "High rate of generic errors/exceptions in logs. Application may be unstable."
                confidence = 0.60
                evidence.append(f"Detected {total_errors} error lines in Loki logs.")

        result = {
            "agent_type": self.agent_type.value,
            "root_cause_category": category.value,
            "root_cause_description": description,
            "confidence": confidence,
            "evidence": evidence,
        }
        logger.info("log_agent_analysis_complete", result=result)
        return result
