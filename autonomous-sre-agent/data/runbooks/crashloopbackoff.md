# CrashLoopBackOff

## Overview
CrashLoopBackOff occurs when a container repeatedly starts and crashes. It usually indicates a bad deployment, missing configuration, or a fatal runtime error.

## Symptoms
- Pod status shows CrashLoopBackOff.
- Restart count increases rapidly.
- Events include "back-off restarting failed container".
- Logs show immediate process exit or repeated exceptions.

## Diagnostics
1. Check pod status:
   - kubectl get pod <pod> -n <namespace>
2. Describe pod and review events:
   - kubectl describe pod <pod> -n <namespace>
3. Review previous container logs:
   - kubectl logs <pod> -n <namespace> --previous
4. Review current logs:
   - kubectl logs <pod> -n <namespace>
5. Verify recent deployment changes and config updates.

## Remediation Steps
1. Roll back the deployment to the last known good revision:
   - kubectl rollout undo deployment/<deployment> -n <namespace>
2. Restart the pod to clear transient failures:
   - kubectl delete pod <pod> -n <namespace>
3. Fix missing env vars, secrets, or config errors and redeploy.
4. If OOMKilled appears, raise memory limits or scale deployment.

## Validation
- Pod transitions to Ready and stays stable.
- CrashLoopBackOff events stop.
- Error rate and latency return to baseline.

## Escalation
- If the crashloop persists after rollback, engage the on-call SRE and application owner.
