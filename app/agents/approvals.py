import datetime as dt
import logging

from sqlalchemy import select

from app.agents.memory import record_memory
from app.agents.tools import get_tool_impl
from app.db.models import ApprovalRequest, Company, Skill, SkillGrant, Task
from app.db.session import session_scope
from app.skills.runtime import run_custom_tool

logger = logging.getLogger("looper.agents.approvals")


async def resolve_approval(approval_id: int, approve: bool) -> None:
    task_id = None
    async with session_scope() as session:
        approval = await session.get(ApprovalRequest, approval_id)
        if not approval or approval.status != "pending":
            return
        approval.status = "approved" if approve else "denied"
        approval.resolved_at = dt.datetime.now(dt.timezone.utc)

        if approval.kind == "skill_grant":
            grant = await session.get(SkillGrant, approval.payload_json["skill_grant_id"])
            if grant:
                grant.status = "approved" if approve else "denied"
                grant.resolved_at = dt.datetime.now(dt.timezone.utc)
            return

        task = await session.get(Task, approval.task_id) if approval.task_id else None
        if not task or approval.kind != "risky_action":
            return

        company = await session.get(Company, task.company_id)
        payload = approval.payload_json
        tool_call_id = payload["tool_call_id"]
        name = payload["tool_name"]
        args = payload["args"]
        skill_id = payload.get("skill_id")

        if approve:
            try:
                if skill_id:
                    skill = await session.get(Skill, skill_id)
                    result_str = run_custom_tool(skill, args, company.folder_path) if skill else f"Error: skill {skill_id} not found."
                else:
                    impl = get_tool_impl(name)
                    result_str = impl(company_folder=company.folder_path, **args) if impl else f"Error: unknown tool '{name}'."
            except Exception as e:
                logger.exception("Approved tool %s failed", name)
                result_str = f"Error running '{name}': {e}"
        else:
            result_str = f"Denied by user. Reason for review: {payload.get('reason', '')}"

        messages = list(task.messages_json)
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": name, "content": str(result_str)})
        task.messages_json = messages
        task.updated_at = dt.datetime.now(dt.timezone.utc)

        await record_memory(session, task.target_agent_id, "tool", f"{name} -> {str(result_str)[:2000]}")

        still_pending = (
            await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.task_id == task.id, ApprovalRequest.status == "pending"
                )
            )
        ).scalars().all()

        if not still_pending:
            task.status = "pending"
            task_id = task.id

    if task_id:
        from app.worker import enqueue_task

        await enqueue_task(task_id)
