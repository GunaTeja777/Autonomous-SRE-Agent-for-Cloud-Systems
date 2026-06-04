# Workflow

## Incident Lifecycle
1. **Monitor**: Collect metrics, logs, traces, and Kubernetes state.
2. **Detect**: Apply thresholds and ML-based anomaly detection.
3. **Classify**: Assign severity and incident targets.
4. **RCA**: Run specialist agents and reconcile via consensus.
5. **Retrieve**: Fetch related runbooks and past incidents.
6. **Plan**: Generate a remediation plan (LLM or rule-based).
7. **Assess Risk**: Decide whether remediation is safe.
8. **Execute**: Apply remediation steps with rollback support.
9. **Verify**: Re-check metrics, logs, and Kubernetes state.
10. **Resolve**: Mark incident as resolved, failed, or needs human review.

## Manual Remediation Approval
If risk assessment rejects automated action, the incident transitions to `needs_human`.
Use the `POST /api/incidents/{id}/approve` endpoint to approve remediation.
