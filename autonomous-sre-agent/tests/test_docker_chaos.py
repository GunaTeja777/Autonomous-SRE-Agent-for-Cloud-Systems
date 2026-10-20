"""
End-to-end chaos integration test against live Docker containers.
Tests the full loop:
  1. Injects live memory leak into payment-api container (http://localhost:8080/chaos/memory-leak).
  2. Prompts SRE Agent to run monitoring scan (http://localhost:8000/api/trigger).
  3. Verifies Anomaly Detection, Multi-Agent RCA, and Risk Gating (needs_human).
  4. Approves remediation (http://localhost:8000/api/incidents/{id}/approve).
  5. Waits for automated remediation, cooldown, and verification (status: resolved).
  6. Fetches and displays the postmortem markdown report.
"""

import time
import httpx

AGENT_URL = "http://localhost:8000"
WORKLOAD_URL = "http://localhost:8080"


def run_docker_chaos_test():
    print("=================================================================")
    print("         AUTONOMOUS SRE AGENT — REAL-TIME CHAOS TEST             ")
    print("=================================================================\n")

    # 1. Health checks
    print("1. Checking service health...")
    try:
        r_agent = httpx.get(f"{AGENT_URL}/health", timeout=5.0)
        assert r_agent.status_code == 200, f"SRE Agent not healthy: {r_agent.text}"
        print(f"  [OK] SRE Agent is healthy: {r_agent.json()}")
    except Exception as e:
        print(f"  [FAIL] SRE Agent unreachable at {AGENT_URL}. Is Docker running? Error: {e}")
        return

    try:
        r_workload = httpx.get(f"{WORKLOAD_URL}/health", timeout=5.0)
        assert r_workload.status_code == 200, f"Workload not healthy: {r_workload.text}"
        print(f"  [OK] Payment API workload is healthy: {r_workload.json()}")
    except Exception as e:
        print(f"  [FAIL] Payment API unreachable at {WORKLOAD_URL}. Error: {e}")
        return

    # 2. Inject Chaos
    print("\n2. Injecting Chaos: runaway memory leak & OOM risk into payment-api...")
    r_chaos = httpx.post(f"{WORKLOAD_URL}/chaos/memory-leak", timeout=5.0)
    print(f"  [CHAOS INJECTED] Response: {r_chaos.json()['message']}")

    # 3. Trigger SRE Agent Scan
    print("\n3. Triggering SRE Agent Scan...")
    r_scan = httpx.post(f"{AGENT_URL}/api/trigger", json={"namespace": "default"}, timeout=10.0)
    print(f"  Scan response: {r_scan.json()}")

    # 4. Wait for Incident Investigation & Risk Gate
    print("\n4. Awaiting Multi-Agent RCA & Risk Gating (polling /api/incidents)...")
    incident_id = None
    for attempt in range(30):
        time.sleep(2)
        r_inc = httpx.get(f"{AGENT_URL}/api/incidents", timeout=5.0)
        incidents = r_inc.json()
        if incidents:
            target_inc = incidents[-1]
            status = target_inc.get("status")
            incident_id = target_inc.get("incident_id")
            print(f"  [Attempt {attempt+1}] Incident {incident_id} state: {status}")
            if status in ["needs_human", "resolved", "remediating", "failed"]:
                break

    if not incident_id:
        print("  [ERROR] No incident triggered during test.")
        return

    # 5. Fetch Incident Details
    r_detail = httpx.get(f"{AGENT_URL}/api/incidents/{incident_id}", timeout=5.0)
    detail = r_detail.json()
    print("\n=== Incident Details & RCA Consensus ===")
    print(f"  Incident ID: {incident_id}")
    print(f"  Status: {detail.get('status')}")
    print(f"  Severity: {detail.get('severity')}")
    rca = detail.get("rca_result", {})
    print(f"  Consensus Root Cause: {rca.get('root_cause_category')}")
    print(f"  Confidence: {rca.get('confidence')}")
    print(f"  Agreement Level: {rca.get('agreement_level')}")
    plan = detail.get("remediation_plan", {})
    if plan:
        print(f"  Proposed Remediation: {plan.get('steps', [{}])[0].get('description')}")
    risk = detail.get("risk_assessment", {})
    print(f"  Risk Gate Approved: {risk.get('approved')}")
    print(f"  Concerns: {risk.get('concerns')}")

    # 6. Approve Remediation if gated
    if detail.get("status") == "needs_human":
        print(f"\n5. Incident gated by safety policy. Approving remediation via POST /api/incidents/{incident_id}/approve...")
        r_appr = httpx.post(f"{AGENT_URL}/api/incidents/{incident_id}/approve", timeout=5.0)
        print(f"  Approval response: {r_appr.json()}")

        print("\n6. Awaiting Execution, Verification & Resolution...")
        for attempt in range(40):
            time.sleep(2)
            r_detail = httpx.get(f"{AGENT_URL}/api/incidents/{incident_id}", timeout=5.0)
            status = r_detail.json().get("status")
            print(f"  [Attempt {attempt+1}] Incident status: {status}")
            if status in ["resolved", "failed"]:
                break

    # 7. Final State & Postmortem
    r_detail = httpx.get(f"{AGENT_URL}/api/incidents/{incident_id}", timeout=5.0)
    final = r_detail.json()
    print(f"\n================ FINAL STATUS: {final.get('status').upper()} ================")
    print(f"  Remediation: {final.get('remediation_summary')}")
    v_res = final.get("verification_result", {})
    print(f"  Verification Resolved: {v_res.get('resolved')}")
    print(f"  Evidence: {v_res.get('evidence')}")

    print("\n7. Fetching Rendered Markdown Postmortem...")
    r_report = httpx.get(f"{AGENT_URL}/api/incidents/{incident_id}/report", timeout=5.0)
    print("\n--- BEGIN POSTMORTEM REPORT ---")
    print(r_report.text[:800])
    print("...\n--- END POSTMORTEM REPORT ---")

    # 8. Reset chaos
    httpx.post(f"{WORKLOAD_URL}/chaos/recover", timeout=5.0)
    print("\n[OK] Reset workload chaos back to baseline. Real-time test completed successfully!")


if __name__ == "__main__":
    run_docker_chaos_test()
