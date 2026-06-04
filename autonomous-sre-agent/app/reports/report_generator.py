import os
from typing import Any
from app.reports.incident_report import IncidentReport
from app.reports.dashboard_export import DashboardExporter
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.exporter = DashboardExporter()

    def generate_incident_report(self, incident_data: dict[str, Any]) -> str:
        """
        Generates and saves a postmortem report markdown file for an incident.
        """
        incident_id = incident_data.get("incident_id", "unknown")
        reporter = IncidentReport(incident_data)
        content = reporter.generate_markdown()
        
        filename = f"postmortem_{incident_id}.md"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, "w") as f:
                f.write(content)
            logger.info("postmortem_report_saved", path=filepath)
            return filepath
        except Exception as e:
            logger.error("failed_to_save_postmortem_report", incident_id=incident_id, error=str(e))
            return ""

    def export_dashboard_data(self, incidents: list[dict[str, Any]]) -> str:
        """
        Export list of all SRE incidents to the dashboard dashboard folder.
        """
        return self.exporter.export_summary(incidents)
