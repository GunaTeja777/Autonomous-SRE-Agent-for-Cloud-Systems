# Image Pull Error (ImagePullBackOff / ErrImagePull)

## Overview
ImagePullBackOff or ErrImagePull indicates the node cannot download the container image from the registry.

## Symptoms
- Pod shows ImagePullBackOff or ErrImagePull.
- Events report failed to pull image or unauthorized.
- Logs reference imagepullbackoff or errimagepull.

## Diagnostics
1. Describe the pod and check image errors:
   - kubectl describe pod <pod> -n <namespace>
2. Verify the image name and tag exist in the registry.
3. Confirm imagePullSecrets are present and correct.
4. Validate node network access to the registry.

## Remediation Steps
1. Fix the image name or tag in the deployment:
   - kubectl set image deployment/<deployment> <container>=<image> -n <namespace>
2. Update or add imagePullSecrets for registry credentials.
3. Roll back the deployment if a recent change caused the failure:
   - kubectl rollout undo deployment/<deployment> -n <namespace>
4. Recreate the pod to force a new pull:
   - kubectl delete pod <pod> -n <namespace>

## Validation
- Pod pulls the image successfully and becomes Ready.
- No new ImagePullBackOff events appear.

## Escalation
- If the registry is down or credentials are blocked, contact the registry/platform team.
