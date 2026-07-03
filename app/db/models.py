from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    folder_path: Mapped[str] = mapped_column(String(1000))
    openrouter_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    heartbeats_enabled: Mapped[bool] = mapped_column(default=True)
    paused: Mapped[bool] = mapped_column(default=False)
    budget_usd_cap: Mapped[Optional[float]] = mapped_column(nullable=True)
    spend_usd_total: Mapped[float] = mapped_column(default=0.0)
    remote_code_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remote_code_version: Mapped[int] = mapped_column(default=0)
    remote_code_set_at: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)

    # Inbound webhook (n8n → Looper)
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Web search (Brave Search API)
    brave_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # n8n automation integration
    n8n_mode: Mapped[str] = mapped_column(String(20), default="self_hosted")
    n8n_project_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    n8n_cloud_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    n8n_cloud_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Email (SMTP/IMAP)
    email_display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email_smtp_host: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    email_smtp_port: Mapped[Optional[int]] = mapped_column(nullable=True)
    email_smtp_username: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    email_smtp_password_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_smtp_use_tls: Mapped[bool] = mapped_column(default=True)
    email_imap_host: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    email_imap_port: Mapped[Optional[int]] = mapped_column(nullable=True)
    email_imap_username: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    email_imap_password_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_imap_use_ssl: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    agents: Mapped[list["Agent"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    skills: Mapped[list["Skill"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    heartbeats: Mapped[list["Heartbeat"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    remote_sessions: Mapped[list["RemoteSession"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    mcp_servers: Mapped[list["McpServer"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    parent_agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    personality: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # active = working normally, vacant = slot exists but no agent assigned a model yet, fired = retired/historical
    status: Mapped[str] = mapped_column(String(20), default="vacant")

    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    fired_at: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)

    company: Mapped["Company"] = relationship(back_populates="agents")
    parent: Mapped[Optional["Agent"]] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["Agent"]] = relationship(
        back_populates="parent", order_by="Agent.id"
    )

    memory_entries: Mapped[list["AgentMemoryEntry"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", order_by="AgentMemoryEntry.id"
    )
    skill_grants: Mapped[list["SkillGrant"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    extra_manager_links: Mapped[list["AgentExtraManager"]] = relationship(
        "AgentExtraManager",
        foreign_keys="[AgentExtraManager.agent_id]",
        cascade="all, delete-orphan",
    )

    @property
    def is_ceo(self) -> bool:
        return self.parent_agent_id is None


class AgentExtraManager(Base):
    __tablename__ = "agent_extra_managers"
    __table_args__ = (UniqueConstraint("agent_id", "manager_id", name="uq_extra_manager"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    manager_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))

    manager: Mapped["Agent"] = relationship("Agent", foreign_keys="[AgentExtraManager.manager_id]")


class AgentMemoryEntry(Base):
    __tablename__ = "agent_memory_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    role: Mapped[str] = mapped_column(String(20))  # user / assistant / tool / system_event
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    agent: Mapped["Agent"] = relationship(back_populates="memory_entries")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    target_agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    parent_task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)

    origin: Mapped[str] = mapped_column(String(20))  # user / heartbeat / delegation / report
    instruction: Mapped[str] = mapped_column(Text)
    origin_tool_call_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # pending / in_progress / delegated / awaiting_approval / completed / failed
    status: Mapped[str] = mapped_column(String(20), default="pending")

    messages_json: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    iterations: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    company: Mapped["Company"] = relationship(back_populates="tasks")
    target_agent: Mapped["Agent"] = relationship(foreign_keys=[target_agent_id])
    parent_task: Mapped[Optional["Task"]] = relationship(remote_side=[id], back_populates="child_tasks")
    child_tasks: Mapped[list["Task"]] = relationship(back_populates="parent_task")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))  # risky_action / skill_grant
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # pending / approved / denied
    status: Mapped[str] = mapped_column(String(20), default="pending")

    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    resolved_at: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    instructions_md: Mapped[str] = mapped_column(Text, default="")
    custom_tool_source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_tool_schema_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # private (owner agent only) / company (any agent in same company) / shop (global, requestable)
    visibility: Mapped[str] = mapped_column(String(20), default="private")

    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    owner_agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    company: Mapped[Optional["Company"]] = relationship(back_populates="skills")
    grants: Mapped[list["SkillGrant"]] = relationship(back_populates="skill", cascade="all, delete-orphan")


class SkillGrant(Base):
    __tablename__ = "skill_grants"
    __table_args__ = (UniqueConstraint("skill_id", "agent_id", name="uq_skill_agent"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))

    # requested / approved / denied / revoked
    status: Mapped[str] = mapped_column(String(20), default="requested")

    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    resolved_at: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)

    skill: Mapped["Skill"] = relationship(back_populates="grants")
    agent: Mapped["Agent"] = relationship(back_populates="skill_grants")


class CachedModel(Base):
    __tablename__ = "cached_models"

    id: Mapped[str] = mapped_column(String(300), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    context_length: Mapped[Optional[int]] = mapped_column(nullable=True)
    supports_tools: Mapped[bool] = mapped_column(default=False)
    pricing_prompt: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pricing_completion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    modality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    refreshed_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True)  # null -> CEO

    name: Mapped[str] = mapped_column(String(200))
    schedule_type: Mapped[str] = mapped_column(String(20))  # interval / once
    schedule_value: Mapped[str] = mapped_column(String(100))  # seconds (interval) or ISO datetime (once)
    instruction_text: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)

    next_run_at: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)
    last_run_at: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    company: Mapped["Company"] = relationship(back_populates="heartbeats")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    model_id: Mapped[str] = mapped_column(String(300))
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class WebSearchRecord(Base):
    __tablename__ = "web_search_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    query: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class RemoteSession(Base):
    __tablename__ = "remote_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    company: Mapped["Company"] = relationship(back_populates="remote_sessions")


class McpServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(200))

    transport: Mapped[str] = mapped_column(String(20))  # stdio / streamable_http
    command: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    args_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    env_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    enabled: Mapped[bool] = mapped_column(default=True)
    cached_tools_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    tools_refreshed_at: Mapped[Optional[dt.datetime]] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    company: Mapped["Company"] = relationship(back_populates="mcp_servers")


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    personality: Mapped[str] = mapped_column(Text, default="")
    recommended_model_id: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class N8nTemplate(Base):
    __tablename__ = "n8n_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    workflow_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    heartbeats_run_when_closed: Mapped[bool] = mapped_column(default=False)
    background_service_installed: Mapped[bool] = mapped_column(default=False)
    remote_access_enabled: Mapped[bool] = mapped_column(default=False)
