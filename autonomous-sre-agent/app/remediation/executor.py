from typing import Any
from app.remediation.kubectl_actions import KubectlActions
from app.remediation.sandbox_validator import SandboxValidator
from app.remediation.rollback_manager import RollbackManager
from app.utils.logger import get_logger
from app.utils.exceptions import RemediationError

logger = get_logger(__name__)


class RemediationExecutor:
    def __init__(self, actions: KubectlActions, validator: SandboxValidator):
        self.actions = actions
        self.validator = validator
        self.rollback_manager = RollbackManager(actions)

    async def execute_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Executes a multi-step remediation plan sequentially with validation and automated rollbacks.
        """
        plan_id = plan.get("plan_id", "unknown")
        steps = plan.get("steps", [])
        logger.info("remediation_execution_start", plan_id=plan_id, steps_count=len(steps))

        executed_steps = []
        if not steps:
            return {
                "success": True,
                "executed_steps": [],
                "message": "No steps to execute in plan.",
            }

        for step in steps:
            num = step.get("step")
            action = step.get("action")
            target = step.get("target")
            params = step.get("params", {})
            rollback_action = step.get("rollback_action", "no_action")

            # 1. Sandbox Validation
            is_valid, validation_reason = await self.validator.validate(action, target, params)
            if not is_valid:
                logger.error("step_validation_failed", step=num, reason=validation_reason)
                # Attempt to roll back any previously completed steps
                await self.rollback_manager.rollback_all()
                return {
                    "success": False,
                    "executed_steps": executed_steps,
                    "message": f"Validation failed on step {num}: {validation_reason}",
                }

            # 2. Execution
            try:
                logger.info("step_executing", step=num, action=action, target=target)
                ok = await self.actions.execute(action, target, params)
                if not ok:
                    logger.error("step_execution_failed_status", step=num)
                    await self.rollback_manager.rollback_all()
                    return {
                        "success": False,
                        "executed_steps": executed_steps,
                        "message": f"Step {num} ({action} on {target}) failed execution.",
                    }

                # Record step for rollback
                self.rollback_manager.record_step(action, target, params, rollback_action)
                executed_steps.append(step)
                logger.info("step_completed_successfully", step=num)

            except Exception as e:
                logger.error("step_execution_error", step=num, error=str(e))
                await self.rollback_manager.rollback_all()
                return {
                    "success": False,
                    "executed_steps": executed_steps,
                    "message": f"Exception during execution of step {num}: {e}",
                }

        logger.info("remediation_execution_completed_successfully", plan_id=plan_id)
        return {
            "success": True,
            "executed_steps": executed_steps,
            "message": "All steps executed successfully.",
        }

    async def trigger_rollback(self) -> bool:
        """
        External API to manually trigger rollback if verification fails.
        """
        logger.info("remediation_rollback_triggered_externally")
        return await self.rollback_manager.rollback_all()
