from sqlalchemy import select

from app.db.models import Agent, Skill, SkillGrant

RESTRICTED_BUILTINS = {
    "len": len, "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple, "range": range,
    "enumerate": enumerate, "zip": zip, "sorted": sorted, "min": min, "max": max,
    "sum": sum, "abs": abs, "round": round, "print": print, "Exception": Exception,
    "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
}


def skill_tool_name(skill: Skill) -> str:
    return f"skill_{skill.id}"


def build_skill_tool_schema(skill: Skill) -> dict:
    schema = dict(skill.custom_tool_schema_json or {"type": "object", "properties": {}, "required": []})
    return {
        "type": "function",
        "function": {
            "name": skill_tool_name(skill),
            "description": f"[Skill: {skill.name}] {skill.description}",
            "parameters": schema,
        },
    }


def build_request_skill_schema(requestable: list[Skill]) -> dict | None:
    if not requestable:
        return None
    options = ", ".join(f"{s.id}={s.name} ({s.description})" for s in requestable)
    return {
        "type": "function",
        "function": {
            "name": "request_skill",
            "description": f"Request access to a Skill Shop skill. Available: {options}. Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {"skill_id": {"type": "integer", "enum": [s.id for s in requestable]}},
                "required": ["skill_id"],
            },
        },
    }


async def build_skill_context(session, agent: Agent) -> dict:
    """Returns the active-skill tool schemas/instructions plus the request_skill schema for an agent."""
    grants = (
        await session.execute(select(SkillGrant).where(SkillGrant.agent_id == agent.id, SkillGrant.status == "approved"))
    ).scalars().all()
    granted_skills = []
    for g in grants:
        skill = await session.get(Skill, g.skill_id)
        if skill:
            granted_skills.append(skill)

    schemas = [build_skill_tool_schema(s) for s in granted_skills if s.custom_tool_source]
    tool_map = {skill_tool_name(s): s.id for s in granted_skills if s.custom_tool_source}
    instructions = "\n\n".join(f"[Skill: {s.name}]\n{s.instructions_md}" for s in granted_skills if s.instructions_md)

    known_skill_ids = {
        g.skill_id
        for g in (await session.execute(select(SkillGrant).where(SkillGrant.agent_id == agent.id))).scalars().all()
    }
    shop_skills = (await session.execute(select(Skill).where(Skill.visibility == "shop"))).scalars().all()
    requestable = [s for s in shop_skills if s.id not in known_skill_ids]
    request_schema = build_request_skill_schema(requestable)

    return {
        "schemas": schemas,
        "tool_map": tool_map,
        "instructions": instructions,
        "request_schema": request_schema,
    }


def run_custom_tool(skill: Skill, args: dict, company_folder: str) -> str:
    if not skill.custom_tool_source:
        return f"Error: skill '{skill.name}' has no executable tool code."
    namespace: dict = {"__builtins__": RESTRICTED_BUILTINS}
    try:
        exec(skill.custom_tool_source, namespace)
        fn = namespace.get("run")
        if not callable(fn):
            return f"Error: skill '{skill.name}' tool code must define a `run(args, company_folder)` function."
        result = fn(args, company_folder)
        return str(result)
    except Exception as e:
        return f"Error running skill '{skill.name}': {e}"
