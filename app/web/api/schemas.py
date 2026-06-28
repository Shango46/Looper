from pydantic import BaseModel


class HireAgentRequest(BaseModel):
    parent_agent_id: int
    name: str
    title: str
    personality: str = ""
    model_id: str


class EditAgentRequest(BaseModel):
    name: str
    title: str
    personality: str = ""
    model_id: str


class ReplaceAgentRequest(BaseModel):
    name: str
    title: str
    personality: str = ""
    model_id: str


class ChatMessageRequest(BaseModel):
    message: str


class InstructRequest(BaseModel):
    instruction: str


class CreateSkillRequest(BaseModel):
    agent_id: int
    name: str
    description: str = ""
    instructions_md: str = ""
    custom_tool_source: str | None = None
    custom_tool_schema_json: dict | None = None
    visibility: str = "private"


class GrantSkillRequest(BaseModel):
    agent_id: int
