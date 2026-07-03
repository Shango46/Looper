import datetime as dt
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.browser import BROWSER_TOOL_NAMES, dispatch_browser_tool
from app.agents.company_tools import COMPANY_TOOL_IMPLS
from app.agents.delegation import create_delegated_child_task, create_report_task, on_task_finished
from app.agents.memory import count_tokens, get_memory_slice, record_memory
from app.agents.risk import evaluate_risk
from app.agents.tools import get_tool_impl, get_tools_for
from app.agents.usage import budget_exceeded, record_usage
from app.config import MAX_TOOL_ITERATIONS, TASK_WALL_CLOCK_TIMEOUT_SECONDS
from app.crypto import decrypt
from app.db.models import Agent, ApprovalRequest, CachedModel, Company, McpServer, Skill, SkillGrant, Task, WebSearchRecord
from app.db.session import session_scope
from app.mcp.client import call_tool as call_mcp_tool
from app.mcp.runtime import build_mcp_context
from app.openrouter.client import OpenRouterError, chat_completion
from app.skills.runtime import build_skill_context

logger = logging.getLogger("looper.agents.loop")


def build_system_prompt(agent: Agent, skill_instructions: str = "") -> str:
    parts = [
        f"You are {agent.name}, {agent.title}.",
        agent.personality or "You are a capable, professional employee who gets things done.",
        "You operate inside a sandboxed company working folder via file tools. "
        "Use tools when you need to read, write, or inspect files. "
        "When you have finished the task (or cannot proceed), reply with plain text — do not call a tool just to announce completion.",
    ]
    if agent.notes:
        parts.append("Your long-term notes (use note_read/note_write to update these across tasks):\n\n" + agent.notes)
    if skill_instructions:
        parts.append("You have been granted the following skills:\n\n" + skill_instructions)
    return "\n\n".join(parts)


async def _load_context(task_id: int) -> dict:
    async with session_scope() as session:
        task = await session.get(Task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        agent = await session.get(Agent, task.target_agent_id, options=[selectinload(Agent.children)])
        company = await session.get(Company, task.company_id)
        model_row = await session.get(CachedModel, agent.model_id) if agent.model_id else None

        active_children = [c for c in agent.children if c.status != "fired"]
        skill_ctx = await build_skill_context(session, agent)
        mcp_ctx = await build_mcp_context(session, company.id)
        tool_schemas = get_tools_for(agent, active_children)
        if skill_ctx["schemas"]:
            tool_schemas += skill_ctx["schemas"]
        if skill_ctx["request_schema"]:
            tool_schemas.append(skill_ctx["request_schema"])
        if mcp_ctx["schemas"]:
            tool_schemas += mcp_ctx["schemas"]

        if not task.messages_json:
            system_prompt = build_system_prompt(agent, skill_ctx["instructions"])
            memory_msgs = await get_memory_slice(
                session, agent, model_row.context_length if model_row else None, count_tokens(system_prompt)
            )
            messages = [{"role": "system", "content": system_prompt}] + memory_msgs + [
                {"role": "user", "content": task.instruction}
            ]
            await record_memory(session, agent.id, "user", task.instruction)
        else:
            messages = list(task.messages_json)

        return {
            "task_id": task.id,
            "company_id": company.id,
            "company_folder": company.folder_path,
            "api_key": decrypt(company.openrouter_api_key_encrypted) if company.openrouter_api_key_encrypted else None,
            "agent_id": agent.id,
            "model_id": agent.model_id,
            "supports_tools": bool(model_row and model_row.supports_tools),
            "messages": messages,
            "iterations": task.iterations,
            "status": task.status,
            "agent_status": agent.status,
            "agent_name": agent.name,
            "tool_schemas": tool_schemas,
            "skill_tool_map": skill_ctx["tool_map"],
            "mcp_tool_map": mcp_ctx["tool_map"],
            "company_ctx": {
                "company_id": company.id,
                "brave_api_key_encrypted": company.brave_api_key_encrypted,
                "email_display_name": company.email_display_name,
                "email_smtp_host": company.email_smtp_host,
                "email_smtp_port": company.email_smtp_port,
                "email_smtp_username": company.email_smtp_username,
                "email_smtp_password_encrypted": company.email_smtp_password_encrypted,
                "email_smtp_use_tls": company.email_smtp_use_tls,
                "email_imap_host": company.email_imap_host,
                "email_imap_port": company.email_imap_port,
                "email_imap_username": company.email_imap_username,
                "email_imap_password_encrypted": company.email_imap_password_encrypted,
                "email_imap_use_ssl": company.email_imap_use_ssl,
            },
        }


async def _persist(
    task_id: int,
    messages: list[dict],
    iterations: int,
    status: str | None = None,
    result: str | None = None,
) -> None:
    async with session_scope() as session:
        task = await session.get(Task, task_id)
        task.messages_json = messages
        task.iterations = iterations
        task.updated_at = dt.datetime.now(dt.timezone.utc)
        if status:
            task.status = status
        if result is not None:
            task.result = result


async def _finish(task_id: int, messages: list[dict], iterations: int, status: str, result: str) -> str:
    await _persist(task_id, messages, iterations, status=status, result=result)
    await on_task_finished(task_id)
    return status


async def run_step(task_id: int) -> str:
    """Drives an agent's tool-calling loop for one task until it reaches a stable state:
    completed, failed, awaiting_approval, or delegated. Returns the resulting status."""
    ctx = await _load_context(task_id)
    if ctx["status"] in ("completed", "failed", "cancelled"):
        return ctx["status"]

    if ctx["agent_status"] == "fired":
        return await _finish(
            task_id, ctx["messages"], ctx["iterations"], "failed",
            f"{ctx['agent_name']} has been fired and cannot process tasks. Replace this position first.",
        )

    agent_id = ctx["agent_id"]
    company_id = ctx["company_id"]
    company_folder = ctx["company_folder"]
    company_ctx = ctx["company_ctx"]
    api_key = ctx["api_key"]
    messages = ctx["messages"]
    iterations = ctx["iterations"]
    tool_schemas = ctx["tool_schemas"]
    skill_tool_map = ctx["skill_tool_map"]
    mcp_tool_map = ctx["mcp_tool_map"]
    started = dt.datetime.now(dt.timezone.utc)

    if not api_key:
        return await _finish(task_id, messages, iterations, "failed", "No OpenRouter API key configured for this company.")

    use_tools = ctx["supports_tools"] and bool(tool_schemas)

    while iterations < MAX_TOOL_ITERATIONS:
        if (dt.datetime.now(dt.timezone.utc) - started).total_seconds() > TASK_WALL_CLOCK_TIMEOUT_SECONDS:
            return await _finish(task_id, messages, iterations, "failed", "Task exceeded wall-clock timeout.")

        async with session_scope() as session:
            task_status = (await session.get(Task, task_id)).status
            company = await session.get(Company, company_id)
            over_budget = budget_exceeded(company)
            cap, spend = company.budget_usd_cap, company.spend_usd_total
            if over_budget:
                company.paused = True

        if task_status == "cancelled":
            return "cancelled"
        if over_budget:
            return await _finish(
                task_id, messages, iterations, "failed",
                f"Company budget cap (${cap:.4f}) reached — spend is ${spend:.4f}. "
                "The company has been paused; raise the cap or resume manually to continue.",
            )

        try:
            response = await chat_completion(
                api_key=api_key,
                model=ctx["model_id"],
                messages=messages,
                tools=tool_schemas if use_tools else None,
            )
        except OpenRouterError as e:
            return await _finish(task_id, messages, iterations, "failed", f"OpenRouter error: {e}")

        usage = response.get("usage") or {}
        choice = (response.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        iterations += 1

        if not tool_calls:
            content = msg.get("content") or "(no response)"
            messages.append({"role": "assistant", "content": content})
            async with session_scope() as session:
                await record_memory(session, agent_id, "assistant", content)
                company = await session.get(Company, company_id)
                await record_usage(session, company, agent_id, task_id, ctx["model_id"], usage)
            return await _finish(task_id, messages, iterations, "completed", content)

        messages.append(
            {
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": tool_calls,
            }
        )
        async with session_scope() as session:
            call_summaries = "; ".join(
                f"{tc['function']['name']}({tc['function'].get('arguments', '')})" for tc in tool_calls
            )
            await record_memory(session, agent_id, "assistant", f"Called: {call_summaries}")
            company = await session.get(Company, company_id)
            await record_usage(session, company, agent_id, task_id, ctx["model_id"], usage)

        needs_approval = False
        needs_delegation_wait = False

        for tc in tool_calls:
            name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}

            if name == "delegate_task":
                async with session_scope() as session:
                    parent_task = await session.get(Task, task_id)
                    child = await create_delegated_child_task(
                        session, parent_task, args.get("target_agent_id"), args.get("instruction", ""), tc["id"]
                    )
                    if child:
                        child_id = child.id
                        needs_delegation_wait = True
                        await record_memory(
                            session, agent_id, "assistant", f"Delegated to agent {args.get('target_agent_id')}: {args.get('instruction', '')}"
                        )
                    else:
                        child_id = None
                if child_id:
                    from app.worker import enqueue_task

                    await enqueue_task(child_id)
                else:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": name,
                            "content": "Error: invalid delegation target — not one of your active direct reports.",
                        }
                    )
                continue

            if name == "report_to_supervisor":
                async with session_scope() as session:
                    agent_row = await session.get(Agent, agent_id)
                    supervisor = await session.get(Agent, agent_row.parent_agent_id) if agent_row.parent_agent_id else None
                    if supervisor:
                        report = await create_report_task(session, supervisor, company_id, args.get("message", ""))
                        report_id = report.id
                        result_str = f"Reported to {supervisor.name}."
                    else:
                        report_id = None
                        result_str = "Error: you have no supervisor."
                if report_id:
                    from app.worker import enqueue_task

                    await enqueue_task(report_id)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result_str})
                async with session_scope() as session:
                    await record_memory(session, agent_id, "tool", f"{name} -> {result_str}")
                continue

            if name in BROWSER_TOOL_NAMES:
                result_str = await dispatch_browser_tool(name, company_id, company_folder, args)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": str(result_str)})
                async with session_scope() as session:
                    await record_memory(session, agent_id, "tool", f"{name} -> {str(result_str)[:2000]}")
                continue

            if name in mcp_tool_map:
                server_id, original_name = mcp_tool_map[name]
                async with session_scope() as session:
                    server = await session.get(McpServer, server_id)
                if not server:
                    result_str = f"Error: MCP server {server_id} no longer exists."
                else:
                    result_str = await call_mcp_tool(server, original_name, args)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": str(result_str)})
                async with session_scope() as session:
                    await record_memory(session, agent_id, "tool", f"{name} -> {str(result_str)[:2000]}")
                continue

            if name == "request_skill":
                async with session_scope() as session:
                    skill_id = args.get("skill_id")
                    skill = await session.get(Skill, skill_id)
                    if not skill or skill.visibility != "shop":
                        result_str = "Error: unknown or unavailable skill."
                    else:
                        existing = (
                            await session.execute(
                                select(SkillGrant).where(SkillGrant.skill_id == skill_id, SkillGrant.agent_id == agent_id)
                            )
                        ).scalars().first()
                        if existing:
                            result_str = f"You already have a '{existing.status}' grant for '{skill.name}'."
                        else:
                            grant = SkillGrant(skill_id=skill_id, agent_id=agent_id, status="requested")
                            session.add(grant)
                            await session.flush()
                            session.add(
                                ApprovalRequest(
                                    task_id=None,
                                    kind="skill_grant",
                                    payload_json={
                                        "skill_grant_id": grant.id,
                                        "skill_name": skill.name,
                                        "agent_id": agent_id,
                                    },
                                    status="pending",
                                )
                            )
                            result_str = f"Requested skill '{skill.name}'. Awaiting user approval."
                    await record_memory(session, agent_id, "tool", f"{name} -> {result_str}")
                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result_str})
                continue

            if name == "note_read":
                async with session_scope() as session:
                    agent_row = await session.get(Agent, agent_id)
                    notes = agent_row.notes or ""
                result_str = notes if notes else "(no notes yet — use note_write to save something)"
                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result_str})
                async with session_scope() as session:
                    await record_memory(session, agent_id, "tool", f"note_read -> {result_str[:200]}")
                continue

            if name == "note_write":
                new_notes = args.get("content", "")
                async with session_scope() as session:
                    agent_row = await session.get(Agent, agent_id)
                    agent_row.notes = new_notes
                    await record_memory(session, agent_id, "tool", f"note_write -> saved {len(new_notes)} chars")
                result_str = f"Notes saved ({len(new_notes)} chars)."
                messages.append({"role": "tool", "tool_call_id": tc["id"], "name": name, "content": result_str})
                continue

            if name in skill_tool_map:
                needs_approval = True
                async with session_scope() as session:
                    session.add(
                        ApprovalRequest(
                            task_id=task_id,
                            kind="risky_action",
                            payload_json={
                                "tool_call_id": tc["id"],
                                "tool_name": name,
                                "args": args,
                                "reason": "Skill-provided tool — requires approval each use.",
                                "skill_id": skill_tool_map[name],
                            },
                            status="pending",
                        )
                    )
                    await record_memory(
                        session, agent_id, "system_event", f"Paused for approval: skill tool {name}"
                    )
                continue

            decision, reason = evaluate_risk(name, args, company_folder)
            if decision == "REQUIRE_APPROVAL":
                needs_approval = True
                async with session_scope() as session:
                    session.add(
                        ApprovalRequest(
                            task_id=task_id,
                            kind="risky_action",
                            payload_json={
                                "tool_call_id": tc["id"],
                                "tool_name": name,
                                "args": args,
                                "reason": reason,
                            },
                            status="pending",
                        )
                    )
                    await record_memory(
                        session, agent_id, "system_event", f"Paused for approval: {name} — {reason}"
                    )
                continue

            company_impl = COMPANY_TOOL_IMPLS.get(name)
            if company_impl:
                try:
                    result_str = company_impl(company_ctx=company_ctx, company_folder=company_folder, **args)
                except TypeError as e:
                    result_str = f"Error: bad arguments for '{name}': {e}"
                except Exception as e:
                    logger.exception("Tool %s failed", name)
                    result_str = f"Error running '{name}': {e}"
                if name == "web_search" and not result_str.startswith("Web search is not available"):
                    async with session_scope() as session:
                        session.add(WebSearchRecord(
                            company_id=company_id,
                            agent_id=agent_id,
                            query=args.get("query", ""),
                        ))
            else:
                impl = get_tool_impl(name)
                if not impl:
                    result_str = f"Error: unknown tool '{name}'."
                else:
                    try:
                        result_str = impl(company_folder=company_folder, **args)
                    except TypeError as e:
                        result_str = f"Error: bad arguments for '{name}': {e}"
                    except Exception as e:
                        logger.exception("Tool %s failed", name)
                        result_str = f"Error running '{name}': {e}"

            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "name": name, "content": str(result_str)}
            )
            async with session_scope() as session:
                await record_memory(session, agent_id, "tool", f"{name} -> {str(result_str)[:2000]}")

        if needs_delegation_wait:
            await _persist(task_id, messages, iterations, status="delegated")
            return "delegated"

        if needs_approval:
            await _persist(task_id, messages, iterations, status="awaiting_approval")
            return "awaiting_approval"

        await _persist(task_id, messages, iterations, status="in_progress")

    return await _finish(task_id, messages, iterations, "failed", "Exceeded max tool iterations.")
