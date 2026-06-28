import json
import logging
import re
from pathlib import Path

from sqlalchemy import select

from app.db.models import AgentTemplate, Skill

logger = logging.getLogger("looper.db.seed")

# Maps a keyword found in the section header to (display_name, default_title)
_AGENT_MAP = {
    "AUDITOR": ("Auditor Agent", "Quality Assurance Auditor"),
    "RESEARCHER": ("Researcher Agent", "Research Analyst"),
    "ARTICLE WRITER": ("Article Writer Agent", "Article Writer"),
    "CEO": ("CEO Agent", "Chief Executive Officer"),
    "PROGRAMMER": ("Programmer Agent", "Software Engineer"),
    "UI/UX DESIGNER": ("UI/UX Designer Agent", "UI/UX Designer"),
    "DATA ANALYST": ("Data Analyst Agent", "Business Intelligence Analyst"),
    "SOCIAL MEDIA": ("Social Media Agent", "Social Media Manager"),
    "MEDIA ASSETS": ("Media Assets Agent", "Media Assets Specialist"),
    "SECURITY": ("Security & Compliance Agent", "Security & Compliance Officer"),
    "PROJECT MANAGER": ("Project Manager Agent", "Project Manager"),
    "FINANCIAL": ("Financial Agent", "Financial Analyst"),
    "SEO": ("SEO Specialist Agent", "SEO Specialist"),
    "COMPETITOR": ("Competitor Intelligence Agent", "Competitive Intelligence Analyst"),
    "USER FEEDBACK": ("User Feedback Agent", "User Support Specialist"),
    "DEVOPS": ("DevOps Agent", "DevOps Engineer"),
    # New agents added in updated agents.txt
    "VECTOR": ("Vector Knowledge Base Agent", "Knowledge Base Architect"),
    "RED TEAM": ("Red Team Agent", "Adversarial Testing Specialist"),
    "LEGAL": ("Legal & Regulatory Agent", "Legal & Regulatory Liaison"),
    "MODEL ROUTER": ("Model Router Agent", "Prompt Optimizer"),
    "USER PERSONA": ("User Persona Agent", "Persona Simulator"),
    "API INTEGRATION":   ("API Integration Agent",    "Integration Specialist"),
    "GRAPHICS DESIGNER": ("Graphics Designer Agent",  "Graphics Designer"),
}


def _parse_agents_txt(filepath: Path) -> list[dict]:
    try:
        raw = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    marker = "COMPLETE AI AGENT WORKFLOW"
    idx = raw.find(marker)
    if idx == -1:
        return []
    raw = raw[idx:]

    # Each agent section is delimited by:  \n---{80}-\nN. THE XXX AGENT\n---{80}-\n
    parts = re.split(r'-{80}\n(\d+\. THE .+)\n-{80}\n', raw)
    # parts = [preamble, header1, body1, header2, body2, ...]

    results = []
    i = 1
    while i < len(parts) - 1:
        header = parts[i]
        body = parts[i + 1]
        i += 2

        body = body.split("=" * 80)[0].strip()
        header_upper = header.upper()

        display_name, title = None, None
        for key, (dn, t) in _AGENT_MAP.items():
            if key in header_upper:
                display_name, title = dn, t
                break

        if display_name is None:
            m = re.match(r'\d+\. THE (.+?)(?:\s+AGENT)?', header, re.IGNORECASE)
            display_name = (m.group(1).strip().title() + " Agent") if m else header.strip()
            title = (m.group(1).strip().title()) if m else header.strip()

        results.append({"name": display_name, "title": title, "personality": body})

    return results


async def seed_agent_templates(agents_txt: Path) -> None:
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        templates = _parse_agents_txt(agents_txt)
        if not templates:
            logger.info("agents.txt not found or not parseable — Agent Shop starts empty")
            return

        existing_names = set(
            (await session.execute(select(AgentTemplate.name))).scalars().all()
        )

        added = 0
        for t in templates:
            if t["name"] not in existing_names:
                session.add(AgentTemplate(
                    name=t["name"],
                    title=t["title"],
                    personality=t["personality"],
                    recommended_model_id=None,
                ))
                added += 1

        if added:
            await session.commit()
            logger.info("Seeded %d new agent templates from agents.txt", added)
        else:
            logger.info("No new agent templates to seed")


async def seed_shop_skills(skills_json: Path) -> None:
    from app.db.session import SessionLocal

    try:
        raw = skills_json.read_text(encoding="utf-8")
        skills_data = json.loads(raw)
    except FileNotFoundError:
        logger.info("skills.txt not found — Skill Shop starts empty")
        return
    except json.JSONDecodeError as exc:
        logger.warning("skills.txt is not valid JSON: %s", exc)
        return

    if not isinstance(skills_data, list):
        logger.warning("skills.txt is not a JSON array — skipping")
        return

    async with SessionLocal() as session:
        existing_names = set(
            (await session.execute(select(Skill.name).where(Skill.visibility == "shop"))).scalars().all()
        )

        added = 0
        for s in skills_data:
            name = s.get("name", "").strip()
            if not name or name in existing_names:
                continue
            schema = s.get("custom_tool_schema_json")
            if isinstance(schema, str):
                try:
                    schema = json.loads(schema)
                except Exception:
                    schema = None
            session.add(Skill(
                name=name,
                description=s.get("description", ""),
                instructions_md=s.get("instructions_md", ""),
                custom_tool_source=s.get("custom_tool_source") or None,
                custom_tool_schema_json=schema,
                visibility="shop",
                company_id=None,
                owner_agent_id=None,
            ))
            added += 1

        if added:
            await session.commit()
            logger.info("Seeded %d new shop skills from skills.txt", added)
        else:
            logger.info("No new shop skills to seed")
