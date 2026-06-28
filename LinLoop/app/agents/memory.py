import tiktoken
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MEMORY_RETENTION_PER_AGENT
from app.db.models import Agent, AgentMemoryEntry

_ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text or ""))


async def record_memory(session: AsyncSession, agent_id: int, role: str, content: str) -> None:
    session.add(AgentMemoryEntry(agent_id=agent_id, role=role, content=content))
    await session.flush()

    total = (
        await session.execute(
            select(func.count()).select_from(AgentMemoryEntry).where(AgentMemoryEntry.agent_id == agent_id)
        )
    ).scalar_one()
    overflow = total - MEMORY_RETENTION_PER_AGENT
    if overflow > 0:
        oldest_ids = (
            await session.execute(
                select(AgentMemoryEntry.id)
                .where(AgentMemoryEntry.agent_id == agent_id)
                .order_by(AgentMemoryEntry.id)
                .limit(overflow)
            )
        ).scalars().all()
        if oldest_ids:
            await session.execute(delete(AgentMemoryEntry).where(AgentMemoryEntry.id.in_(oldest_ids)))


async def get_memory_slice(
    session: AsyncSession,
    agent: Agent,
    context_length: int | None,
    system_prompt_tokens: int,
    output_reserve: int = 2000,
) -> list[dict]:
    """Most-recent-first accumulation up to a token budget, returned in chronological order.
    Always force-includes the newest entry (truncated) so context is never empty."""
    context_length = context_length or 8192
    budget = max(int(context_length * 0.6) - system_prompt_tokens - output_reserve, 500)

    entries = (
        await session.execute(
            select(AgentMemoryEntry)
            .where(AgentMemoryEntry.agent_id == agent.id)
            .order_by(AgentMemoryEntry.id.desc())
            .limit(MEMORY_RETENTION_PER_AGENT)
        )
    ).scalars().all()

    selected: list[AgentMemoryEntry] = []
    used = 0
    for entry in entries:
        tokens = count_tokens(entry.content)
        if used + tokens > budget:
            if not selected:
                truncated = entry.content[: budget * 3]
                selected.append(
                    AgentMemoryEntry(agent_id=agent.id, role=entry.role, content=truncated)
                )
            break
        selected.append(entry)
        used += tokens

    selected.reverse()
    # AgentMemoryEntry stores a flattened, human-readable narrative (tool calls/results included
    # as descriptive text, never raw tool_call/tool-role API structures) so it can always be safely
    # replayed as plain user/assistant turns at the start of a brand-new task's conversation.
    role_map = {"user": "user", "assistant": "assistant", "tool": "assistant", "system_event": "user"}
    return [{"role": role_map.get(e.role, "user"), "content": e.content} for e in selected]
