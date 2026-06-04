from typing import Any
from app.constants import RootCauseCategory, AgentType
from app.utils.logger import get_logger
from app.llm.chains import ConsensusChain
from app.llm.llm_client import LLMClient

logger = get_logger(__name__)


class ConsensusAgent:
    def __init__(self, llm_client: LLMClient | None = None):
        self.agent_type = AgentType.CONSENSUS
        self.llm_client = llm_client
        self.consensus_chain = ConsensusChain(llm_client) if llm_client else None

    async def run(self, agent_outputs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Combine findings from Metric, Log, Trace, and Kubernetes agents.
        Uses a weighted confidence formula and fallback to LLM consensus.
        """
        logger.info("consensus_agent_run_start", agent_count=len(agent_outputs))

        # Filter out unknown/zero-confidence findings
        valid_findings = [f for f in agent_outputs if f.get("root_cause_category") != RootCauseCategory.UNKNOWN.value and f.get("confidence", 0.0) > 0.0]

        if not valid_findings:
            # If no agent has a high-confidence cause, return unknown
            return {
                "agent_type": self.agent_type.value,
                "root_cause_category": RootCauseCategory.UNKNOWN.value,
                "root_cause_description": "No consensus reached. Specialist agents did not detect any anomalous patterns.",
                "confidence": 0.0,
                "agreement_level": "unknown",
                "dissenting_views": [],
                "final_recommendation": "no_action",
            }

        # Programmatic consensus calculation
        # Group by category and gather confidences
        groups: dict[str, list[float]] = {}
        descriptions: dict[str, list[str]] = {}
        for f in valid_findings:
            cat = f["root_cause_category"]
            groups.setdefault(cat, []).append(f["confidence"])
            descriptions.setdefault(cat, []).append(f["root_cause_description"])

        # Calculate average confidence per category
        category_averages = {cat: sum(confs) / len(confs) for cat, confs in groups.items()}
        # Get the category with highest average confidence
        consensus_category = max(category_averages, key=category_averages.get)
        consensus_confidence = category_averages[consensus_category]

        # Combine descriptions
        combined_description = "; ".join(set(descriptions[consensus_category]))

        # Calculate agreement level
        # If all voting agents chose the same category: full. Else: partial
        total_voters = len(valid_findings)
        consensus_voters = len(groups[consensus_category])
        agreement_level = "full" if consensus_voters == total_voters else "partial"

        # List dissenting views
        dissenting_views = []
        for cat, confs in groups.items():
            if cat != consensus_category:
                avg_conf = sum(confs) / len(confs)
                dissenting_views.append(f"Agent(s) suggested '{cat}' with avg confidence {avg_conf:.1%}")

        # Try LLM consensus if client is configured
        if self.llm_client and self.llm_client._get_client() != "mock":
            try:
                llm_result = await self.consensus_chain.run(agent_outputs)
                logger.info("consensus_agent_llm_success", result=llm_result)
                return {
                    "agent_type": self.agent_type.value,
                    "root_cause_category": llm_result.get("consensus_root_cause", consensus_category),
                    "root_cause_description": llm_result.get("consensus_description", combined_description),
                    "confidence": llm_result.get("overall_confidence", consensus_confidence),
                    "agreement_level": llm_result.get("agreement_level", agreement_level),
                    "dissenting_views": llm_result.get("dissenting_views", dissenting_views),
                    "final_recommendation": llm_result.get("final_recommendation", "monitor"),
                }
            except Exception as e:
                logger.warning("consensus_agent_llm_failed_falling_back", error=str(e))

        # Default programmatic response matches user's request formula
        # Final recommendation based on category
        rec_actions = {
            RootCauseCategory.MEMORY_LEAK.value: "scale_deployment",
            RootCauseCategory.RESOURCE_EXHAUSTION.value: "scale_deployment",
            RootCauseCategory.CRASHLOOP.value: "restart_pod",
            RootCauseCategory.IMAGE_PULL.value: "rollback_deployment",
            RootCauseCategory.CONFIG_ERROR: "update_config",
            RootCauseCategory.NODE_FAILURE: "drain_node",
            RootCauseCategory.NETWORK_ISSUE: "monitor",
            RootCauseCategory.DEPENDENCY_FAILURE: "monitor",
        }
        rec_action = rec_actions.get(consensus_category, "no_action")

        result = {
            "agent_type": self.agent_type.value,
            "root_cause_category": consensus_category,
            "root_cause_description": combined_description,
            "confidence": round(consensus_confidence, 2),
            "agreement_level": agreement_level,
            "dissenting_views": dissenting_views,
            "final_recommendation": rec_action,
        }
        logger.info("consensus_agent_run_complete", result=result)
        return result
