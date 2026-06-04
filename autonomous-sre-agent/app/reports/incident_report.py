from typing import Any
import json

class IncidentReport:
    def __init__(self, incident_data: dict[str, Any]):
        self.data = incident_data

    def generate_markdown(self) -> str:
        """Generates a professional SRE Incident Postmortem Report in Markdown."""
        rca = self.data.get("rca_result", {})
        remediation = self.data.get("remediation_plan", {})
        exec_res = self.data.get("execution_result", {})
        verification = self.data.get("verification_result", {})

        md = [
            f"# SRE Incident Postmortem: {self.data.get('incident_id')}",
            f"**Status**: {self.data.get('status', 'unknown').upper()}",
            f"**Severity**: {self.data.get('severity', 'unknown').upper()}",
            "",
            "## 1. Executive Summary",
            f"- **Target Pod**: `{self.data.get('pod')}`",
            f"- **Namespace**: `{self.data.get('namespace')}`",
            f"- **Detected At**: {self.data.get('detected_at')}",
            f"- **Updated At**: {self.data.get('updated_at')}",
            f"- **Root Cause**: {rca.get('root_cause_description', 'N/A')}",
            f"- **Resolution Summary**: {self.data.get('remediation_summary', 'N/A')}",
            "",
            "## 2. Root Cause Analysis (RCA)",
            f"- **Determined Root Cause Category**: `{rca.get('root_cause_category', 'unknown')}`",
            f"- **Confidence Score**: {rca.get('confidence', 0.0):.1%}",
            f"- **Reasoning**: {rca.get('reasoning', 'N/A')}",
            "",
            "### 2.1 Anomaly Signals Detected",
        ]

        signals = self.data.get("anomaly_report", {}).get("signals", [])
        if signals:
            for sig in signals:
                md.append(f"- {sig}")
        else:
            md.append("- No specific anomaly signals recorded.")

        md.extend([
            "",
            "## 3. Remediation Execution Plan",
            f"- **Remediation Plan ID**: `{remediation.get('plan_id', 'N/A')}`",
            f"- **Risk Level**: `{remediation.get('risk_level', 'N/A')}`",
            f"- **Rationale**: {remediation.get('rationale', 'N/A')}",
            "",
            "### 3.1 Execution Steps",
        ])

        steps = remediation.get("steps", [])
        if steps:
            for step in steps:
                md.append(
                    f"1. **Action**: `{step.get('action')}` on target `{step.get('target')}`"
                )
                md.append(f"   - *Description*: {step.get('description')}")
                md.append(f"   - *Rollback step*: `{step.get('rollback_action')}`")
        else:
            md.append("- No remediation steps executed.")

        md.extend([
            "",
            "## 4. Verification and Recovery Checks",
            f"- **Verification Outcome**: {'RESOLVED' if verification.get('resolved') else 'UNRESOLVED'}",
            f"- **Confidence Level**: {verification.get('confidence', 0.0):.1%}",
            "",
            "### 4.1 Verification Evidence",
        ])

        evidence = verification.get("evidence", [])
        if evidence:
            for ev in evidence:
                md.append(f"- [x] {ev}")
        else:
            md.append("- No verification evidence recorded.")

        issues = verification.get("remaining_issues", [])
        if issues:
            md.extend([
                "",
                "### 4.2 Remaining Issues / Action Items",
            ])
            for iss in issues:
                md.append(f"- [ ] {iss}")

        # Add error messages if any
        if self.data.get("error_message"):
            md.extend([
                "",
                "## 5. Execution Failures / Warnings",
                f"```text\n{self.data.get('error_message')}\n```",
            ])

        return "\n".join(md)
