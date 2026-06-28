from app.db.models import Company, UsageRecord


async def record_usage(session, company: Company, agent_id: int, task_id: int, model_id: str, usage: dict) -> None:
    if not usage:
        return
    cost = float(usage.get("cost") or 0.0)
    session.add(
        UsageRecord(
            company_id=company.id,
            agent_id=agent_id,
            task_id=task_id,
            model_id=model_id,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cost_usd=cost,
        )
    )
    company.spend_usd_total += cost


def budget_exceeded(company: Company) -> bool:
    return company.budget_usd_cap is not None and company.spend_usd_total >= company.budget_usd_cap
