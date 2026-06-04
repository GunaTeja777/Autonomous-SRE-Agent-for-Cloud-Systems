# Node Failure / NotReady

## Overview
Node failures or NotReady conditions can evict pods, block scheduling, and degrade service.

## Symptoms
- Node status is NotReady or Unknown.
- Pods remain Pending with FailedScheduling events.
- Events mention node out of disk, network issues, or pressure.

## Diagnostics
1. Check node status:
   - kubectl get nodes
2. Describe the node for conditions and events:
   - kubectl describe node <node>
3. Review pod scheduling events in the affected namespace.

## Remediation Steps
1. Cordon the failing node to stop new scheduling:
   - kubectl cordon <node>
2. Drain the node to move workloads safely:
   - kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
3. Replace or repair the node at the infrastructure layer.
4. Verify workloads reschedule on healthy nodes.

## Validation
- Pods are Running on healthy nodes.
- FailedScheduling events stop.
- Node is repaired or removed from the cluster.

## Escalation
- If multiple nodes are affected, engage the platform team immediately.
