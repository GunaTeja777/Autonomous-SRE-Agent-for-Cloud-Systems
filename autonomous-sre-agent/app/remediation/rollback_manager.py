from typing import Any
from app.remediation.kubectl_actions import KubectlActions
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RollbackManager:
    def __init__(self, actions: KubectlActions):
        self.actions = actions
        self._history: list[dict[str, Any]] = []

    def record_step(self, action: str, target: str, params: dict[str, Any], rollback_action: str) -> None:
        """
        Record an executed remediation step to allow rollback later if verification fails.
        """
        self._history.append({
            "action": action,
            "target": target,
            "params": params,
            "rollback_action": rollback_action,
        })
        logger.info("remediation_step_recorded_for_rollback", action=action, rollback=rollback_action)

    async def rollback_all(self) -> bool:
        """
        Rollback all recorded steps in reverse order of execution.
        """
        if not self._history:
            logger.info("rollback_no_steps_recorded")
            return True

        logger.info("rollback_started", total_steps=len(self._history))
        success = True

        for step in reversed(self._history):
            rollback_action = step["rollback_action"]
            target = step["target"]
            params = step["params"]

            if not rollback_action or rollback_action == "no_action":
                logger.info("rollback_step_skipped_no_action", target=target)
                continue

            try:
                logger.info("rollback_step_executing", rollback_action=rollback_action, target=target)
                # For rollbacks, we might need custom rollback parameters
                # e.g., if we scaled deployment from N to M, rollback should scale from M back to N.
                # Let's try to extract previous state if stored in params.
                rollback_params = params.copy()
                if "previous_replicas" in params:
                    rollback_params["replicas"] = params["previous_replicas"]

                ok = await self.actions.execute(rollback_action, target, rollback_params)
                if not ok:
                    success = False
                    logger.error("rollback_step_failed", rollback_action=rollback_action, target=target)
            except Exception as e:
                success = False
                logger.error("rollback_step_error", rollback_action=rollback_action, target=target, error=str(e))

        logger.info("rollback_completed", success=success)
        return success
