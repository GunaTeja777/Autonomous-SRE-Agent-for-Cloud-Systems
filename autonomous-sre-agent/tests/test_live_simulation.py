import asyncio
from app.orchestrator.incident_orchestrator import IncidentOrchestrator
from app.reports.incident_report import IncidentReport


async def run_live_simulation():
    print("=================================================================")
    print("      AUTONOMOUS SRE AGENT — REAL-TIME LIVE SIMULATION           ")
    print("=================================================================\n")

    # 1. Initialize
    print("=== 1. Initializing Incident Orchestrator ===")
    orchestrator = IncidentOrchestrator()
    print("Orchestrator initialized with multi-agent consensus & Gemini LLM.\n")

    # 2. Run monitoring tick
    print("=== 2. Running Monitoring Scan (Namespace: 'default') ===")
    triggered = await orchestrator.run_tick("default")
    print(f"Scan completed. Triggered incidents count: {len(triggered)}")

    if not triggered:
        print("No incident triggered.")
        return

    incident = triggered[0]
    incident_id = incident.incident_id
    print(f"\n[ACTIVE INCIDENT DETECTED]")
    print(f"  Incident ID : {incident_id}")
    print(f"  Pod Target  : {incident.pod}")
    print(f"  Severity    : {incident.severity.value.upper()}")
    print(f"  Signals     : {incident.anomaly_report.get('signals')}")

    # 3. Wait for RCA & Planning Phase
    print("\n=== 3. Executing Multi-Agent Diagnostics & Gemini Reasoning ===")
    task1 = orchestrator._active_tasks.get(incident_id)
    if task1:
        await task1

    curr = orchestrator.state_manager.get_incident(incident_id)
    print(f"\nWorkflow reached checkpoint status: {curr.status.value.upper()}")

    print("\n--- Diagnostic Findings & Multi-Agent Consensus ---")
    rca = curr.rca_result or {}
    print(f"  Consensus Root Cause : {rca.get('root_cause_category')}")
    print(f"  Confidence Score     : {rca.get('confidence')}")
    print(f"  Specialist Agreement : {rca.get('agreement_level')}")
    print(f"  Root Cause Summary   : {rca.get('root_cause_description')}")

    print("\n--- Proposed Remediation Plan ---")
    plan = curr.remediation_plan or {}
    print(f"  Plan ID     : {plan.get('plan_id')}")
    print(f"  Risk Level  : {plan.get('risk_level')}")
    for s in plan.get("steps", []):
        print(f"  Step {s.get('step')}: {s.get('action')} on {s.get('target')} -> {s.get('description')}")

    print("\n--- Safety & Risk Gate Evaluation ---")
    risk = curr.risk_assessment or {}
    print(f"  Auto-Execution Approved : {risk.get('approved')}")
    print(f"  Risk Recommendation     : {risk.get('recommendation')}")
    print(f"  Safety Concerns         : {risk.get('concerns')}")

    # 4. Human Approval
    if curr.status.value == "needs_human":
        print(f"\n=== 4. Human-In-The-Loop: Simulating SRE Approval (POST /api/incidents/{incident_id}/approve) ===")
        approved = await orchestrator.trigger_manual_remediation(incident_id)
        print(f"Approval registered. Action execution triggered: {approved}")

        # Wait for Execution, Cooldown & Verification
        print("\n=== 5. Executing Remediation, Cooldown & Verification ===")
        task2 = orchestrator._active_tasks.get(incident_id)
        if task2:
            await task2

    # 5. Final State
    final_incident = orchestrator.state_manager.get_incident(incident_id)
    print(f"\n=================================================================")
    print(f"             FINAL INCIDENT STATE: {final_incident.status.value.upper()}             ")
    print(f"=================================================================")
    print(f"  Remediation Action : {final_incident.remediation_summary}")
    v_res = final_incident.verification_result or {}
    print(f"  Verification Result: {'PASSED (System Recovered)' if v_res.get('resolved') else 'FAILED'}")
    print(f"  Recovery Evidence  : {v_res.get('evidence')}")

    # 6. Postmortem
    print("\n=== 6. Auto-Generated Postmortem Markdown Report ===")
    reporter = IncidentReport(final_incident.to_dict())
    report_md = reporter.generate_markdown()
    print(report_md[:800])
    print("\n... [Full Postmortem Report Generated and Indexed in Vector DB]\n")


if __name__ == "__main__":
    asyncio.run(run_live_simulation())
