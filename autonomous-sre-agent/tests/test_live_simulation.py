import asyncio
import json
from app.orchestrator.incident_orchestrator import IncidentOrchestrator
from app.reports.incident_report import IncidentReport


async def run_live_simulation():
    print("=== 1. Initializing Incident Orchestrator ===")
    orchestrator = IncidentOrchestrator()
    
    print("\n=== 2. Running Loop Tick (Scan Namespace: 'default') ===")
    triggered = await orchestrator.run_tick("default")
    print(f"Triggered incidents count: {len(triggered)}")
    
    if not triggered:
        print("No incident triggered.")
        return

    incident = triggered[0]
    incident_id = incident.incident_id
    print(f"Active Incident ID: {incident_id}")
    print(f"Pod: {incident.pod}, Severity: {incident.severity.value}")
    print(f"Signals: {incident.anomaly_report.get('signals')}")

    # Wait for the background workflow task to reach the approval gate
    print("\n=== 3. Waiting for Multi-Agent RCA & Risk Gate ===")
    for _ in range(30):
        await asyncio.sleep(1)
        curr = orchestrator.state_manager.get_incident(incident_id)
        if curr.status in ["needs_human", "resolved", "failed"]:
            print(f"Incident reached state: {curr.status}")
            break
        print(f"Current State: {curr.status}...")

    curr = orchestrator.state_manager.get_incident(incident_id)
    print("\n=== Specialist Findings & Consensus ===")
    print(f"Consensus Category: {curr.rca_result.get('root_cause_category')}")
    print(f"Consensus Confidence: {curr.rca_result.get('confidence')}")
    print(f"Consensus Agreement: {curr.rca_result.get('agreement_level')}")
    
    print("\n=== Proposed Remediation Plan ===")
    if curr.remediation_plan:
        print(f"Plan ID: {curr.remediation_plan.get('plan_id')}")
        print(f"Risk Level: {curr.remediation_plan.get('risk_level')}")
        for s in curr.remediation_plan.get("steps", []):
            print(f"  Step {s.get('step')}: {s.get('action')} on {s.get('target')} - {s.get('description')}")

    print("\n=== Risk Assessment Gate ===")
    print(f"Approved: {curr.risk_assessment.get('approved')}")
    print(f"Recommendation: {curr.risk_assessment.get('recommendation')}")
    print(f"Concerns: {curr.risk_assessment.get('concerns')}")

    if curr.status == "needs_human":
        print("\n=== 4. Simulating Operator Approval (POST /api/incidents/{id}/approve) ===")
        approved = await orchestrator.trigger_manual_remediation(incident_id)
        print(f"Manual approval trigger result: {approved}")

        # Wait for execution & verification
        print("\n=== 5. Waiting for Execution, Cooldown & Verification ===")
        for _ in range(40):
            await asyncio.sleep(1)
            curr = orchestrator.state_manager.get_incident(incident_id)
            if curr.status in ["resolved", "failed"]:
                print(f"Final State: {curr.status}")
                break
            print(f"Progressing State: {curr.status}...")

    final_incident = orchestrator.state_manager.get_incident(incident_id)
    print(f"\n=== Final Incident State: {final_incident.status.upper()} ===")
    if final_incident.remediation_summary:
        print(f"Remediation Applied: {final_incident.remediation_summary}")
    if final_incident.verification_result:
        print(f"Verification Resolved: {final_incident.verification_result.get('resolved')}")
        print(f"Verification Evidence: {final_incident.verification_result.get('evidence')}")

    print("\n=== 6. Generating Postmortem Markdown Report ===")
    reporter = IncidentReport(final_incident.to_dict())
    report_md = reporter.generate_markdown()
    print("Report generated successfully! (First 500 chars):")
    print(report_md[:500])
    print("...\n[Full Report Ready]")


if __name__ == "__main__":
    asyncio.run(run_live_simulation())
