import json
import os
from typing import Any
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DashboardExporter:
    def __init__(self, export_dir: str = "./data/dashboards"):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    def export_summary(self, incidents: list[dict[str, Any]]) -> str:
        """
        Exports SRE incidents summary data to a JSON file for the dashboard frontend.
        """
        total_incidents = len(incidents)
        resolved_count = sum(1 for inc in incidents if inc.get("status") == "resolved")
        failed_count = sum(1 for inc in incidents if inc.get("status") == "failed")
        investigating_count = sum(1 for inc in incidents if inc.get("status") in ["investigating", "rca_in_progress", "remediating", "verifying"])
        needs_human_count = sum(1 for inc in incidents if inc.get("status") == "needs_human")

        # Summarize by categories
        categories: dict[str, int] = {}
        for inc in incidents:
            cat = inc.get("rca_result", {}).get("root_cause_category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        summary = {
            "metrics": {
                "total": total_incidents,
                "resolved": resolved_count,
                "failed": failed_count,
                "investigating": investigating_count,
                "needs_human": needs_human_count,
                "resolution_rate": (resolved_count / total_incidents) if total_incidents > 0 else 0.0,
            },
            "root_cause_distribution": categories,
            "incidents": [
                {
                    "incident_id": inc.get("incident_id"),
                    "pod": inc.get("pod"),
                    "namespace": inc.get("namespace"),
                    "status": inc.get("status"),
                    "severity": inc.get("severity"),
                    "detected_at": inc.get("detected_at"),
                    "root_cause": inc.get("rca_result", {}).get("root_cause_category", "unknown"),
                    "remediation": inc.get("remediation_summary", "N/A"),
                }
                for inc in incidents
            ],
        }

        export_path = os.path.join(self.export_dir, "summary.json")
        try:
            with open(export_path, "w") as f:
                json.dump(summary, f, indent=2)
            logger.info("dashboard_summary_exported", path=export_path)
            return export_path
        except Exception as e:
            logger.error("dashboard_export_failed", error=str(e))
            return ""
