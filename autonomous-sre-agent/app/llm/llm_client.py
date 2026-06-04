import json
from typing import Any
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.exceptions import LLMClientError

logger = get_logger(__name__)


class LLMClient:
    def __init__(self):
        self.settings = get_settings()
        self.client = None

    def _get_client(self):
        if self.client is None:
            # Check if key is present and not dummy/placeholder
            api_key = self.settings.anthropic_api_key
            if not api_key or api_key == "PLACEHOLDER" or "your_" in api_key.lower():
                logger.warning("anthropic_api_key_not_provided_using_mock")
                self.client = "mock"
            else:
                try:
                    import anthropic
                    self.client = anthropic.AsyncAnthropic(api_key=api_key)
                except Exception as e:
                    logger.error("failed_to_initialize_anthropic_client", error=str(e))
                    self.client = "mock"
        return self.client

    async def acomplete(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        if client == "mock":
            return self._mock_response(system_prompt, user_prompt)

        try:
            logger.info("llm_call_start", model=self.settings.llm_model)
            response = await client.messages.create(
                model=self.settings.llm_model,
                max_tokens=self.settings.llm_max_tokens,
                temperature=self.settings.llm_temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            logger.info("llm_call_completed")
            content = response.content[0].text
            return content
        except Exception as e:
            logger.error("llm_call_failed", error=str(e))
            raise LLMClientError(f"Anthropic LLM call failed: {e}") from e

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """Fallback mock responses that return logically consistent JSON formats."""
        if "RCA_SYSTEM_PROMPT" in system_prompt or "root_cause_category" in user_prompt:
            category = "unknown"
            desc = "An unexpected error occurred."
            if "oomkilled" in user_prompt.lower() or "oom" in user_prompt.lower():
                category = "memory_leak"
                desc = "The application process was terminated due to out-of-memory limits."
            elif "crashloopbackoff" in user_prompt.lower() or "crash" in user_prompt.lower():
                category = "crashloop"
                desc = "The container is crashing repeatedly during startup."
            elif "imagepullbackoff" in user_prompt.lower() or "image" in user_prompt.lower():
                category = "image_pull"
                desc = "Failed to pull image from registry."
            elif "cpu" in user_prompt.lower() or "exceeded threshold" in user_prompt.lower():
                category = "resource_exhaustion"
                desc = "High resource utilisation is starving the process."
            elif "network" in user_prompt.lower() or "timeout" in user_prompt.lower():
                category = "network_issue"
                desc = "Connection timeout trying to reach external services."

            return json.dumps({
                "root_cause_category": category,
                "root_cause_description": desc,
                "confidence": 0.91,
                "contributing_factors": ["High resource utilization", "Frequent restarts"],
                "recommended_actions": ["scale_deployment", "restart_pod"],
                "requires_human": False,
                "reasoning": "Detected OOM killed logs and restarts, indicating resource exhaustion or memory leak."
            })
        elif "REMEDIATION_PLAN_SYSTEM" in system_prompt or "remediation" in user_prompt.lower():
            # mock remediation plan
            # Extract namespace and target pod name if possible
            import re
            target = "api-deployment"
            match = re.search(r"Pod/Deployment:\s*([^\n\r]+)", user_prompt)
            if match:
                target = match.group(1).strip()
            
            # Extract category to match recommended action
            action = "restart_pod"
            if "memory_leak" in user_prompt or "resource_exhaustion" in user_prompt:
                action = "scale_deployment"
            elif "image_pull" in user_prompt:
                action = "rollback_deployment"

            return json.dumps({
                "plan_id": "PLAN-MOCK",
                "steps": [
                    {
                        "step": 1,
                        "action": action,
                        "target": target,
                        "params": {"replicas": 5} if action == "scale_deployment" else {},
                        "description": f"Perform {action} on {target}",
                        "rollback_action": "no_action"
                    }
                ],
                "estimated_recovery_time_seconds": 60,
                "risk_level": "low",
                "rationale": "Recommended action to recover pod state."
            })
        elif "RISK_ASSESSMENT_SYSTEM" in system_prompt or "risk" in user_prompt.lower():
            return json.dumps({
                "approved": True,
                "risk_level": "low",
                "risk_factors": ["No destructive commands being run"],
                "concerns": [],
                "recommendation": "proceed"
            })
        elif "VERIFICATION_SYSTEM" in system_prompt or "verification" in user_prompt.lower() or "resolved" in user_prompt.lower():
            return json.dumps({
                "resolved": True,
                "confidence": 0.95,
                "evidence": ["CPU recovered", "Logs stop", "Pods healthy"],
                "remaining_issues": [],
                "recommendation": "close"
            })
        elif "CONSENSUS_SYSTEM" in system_prompt or "consensus" in user_prompt.lower():
            return json.dumps({
                "consensus_root_cause": "memory_leak",
                "consensus_description": "Specialist agents agree on memory leak",
                "overall_confidence": 0.91,
                "agreement_level": "full",
                "dissenting_views": [],
                "final_recommendation": "scale_deployment"
            })

        return "{}"