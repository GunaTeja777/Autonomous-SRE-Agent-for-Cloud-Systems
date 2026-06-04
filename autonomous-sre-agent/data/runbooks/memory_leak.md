# Memory Leak / OOMKilled

## Overview
Sustained memory growth can trigger OOMKilled events, forcing the container to restart and causing instability.

## Symptoms
- Pod restarts with OOMKilled in events or logs.
- Memory usage stays above 90%.
- Latency increases due to GC pressure.

## Diagnostics
1. Check memory usage:
   - kubectl top pod <pod> -n <namespace>
2. Describe the pod for OOMKilled reasons:
   - kubectl describe pod <pod> -n <namespace>
3. Review logs for out of memory or heap errors.
4. Inspect resource requests/limits in the deployment.

## Remediation Steps
1. Scale the deployment to distribute load:
   - kubectl scale deployment/<deployment> --replicas=5 -n <namespace>
2. Increase memory requests/limits if safe and approved.
3. Restart the pod to recover quickly:
   - kubectl delete pod <pod> -n <namespace>
4. Roll back to a prior image if the leak started after a deployment.

## Validation
- Memory usage stabilizes below the threshold.
- No new OOMKilled events occur.
- Error rate and latency return to normal.

## Escalation
- If leaks persist, capture heap profiles and engage the owning team for a fix.
