import json
import re
from typing import Any
from app.utils.logger import get_logger
from app.utils.exceptions import LLMClientError

logger = get_logger(__name__)


def parse_json_response(raw: str) -> dict[str, Any]:
    """Parse LLM JSON response, stripping markdown fences if present."""
    raw = raw.strip()

    # Strip ```json ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    if fence_match:
        raw = fence_match.group(1).strip()

    # Find first { ... } block
    brace_match = re.search(r"\{[\s\S]+\}", raw)
    if brace_match:
        raw = brace_match.group(0)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("llm_json_parse_failed", error=str(e), raw_preview=raw[:300])
        raise LLMClientError(f"Failed to parse LLM JSON output: {e}") from e


def parse_rca_response(raw: str) -> dict[str, Any]:
    data = parse_json_response(raw)
    required = ["root_cause_category", "root_cause_description", "confidence", "recommended_actions"]
    for key in required:
        if key not in data:
            logger.warning("rca_response_missing_key", key=key)
            data.setdefault(key, "unknown" if key != "confidence" else 0.0)
    data["confidence"] = float(data.get("confidence", 0.0))
    return data


def parse_remediation_plan(raw: str) -> dict[str, Any]:
    data = parse_json_response(raw)
    data.setdefault("steps", [])
    data.setdefault("risk_level", "high")
    return data


def parse_risk_assessment(raw: str) -> dict[str, Any]:
    data = parse_json_response(raw)
    data.setdefault("approved", False)
    data.setdefault("risk_level", "high")
    data.setdefault("recommendation", "human_review")
    return data


def parse_verification_result(raw: str) -> dict[str, Any]:
    data = parse_json_response(raw)
    data.setdefault("resolved", False)
    data.setdefault("confidence", 0.0)
    data["confidence"] = float(data["confidence"])
    return data


def parse_consensus_result(raw: str) -> dict[str, Any]:
    data = parse_json_response(raw)
    data.setdefault("overall_confidence", 0.0)
    data["overall_confidence"] = float(data["overall_confidence"])
    return data