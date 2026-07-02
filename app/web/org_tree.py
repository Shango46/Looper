from app.db.models import Agent


class TreeNode:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.children: list["TreeNode"] = []

    @property
    def active_child_count(self) -> int:
        return len([c for c in self.children if c.agent.status != "fired"])


def build_mermaid_chart(agents: list[Agent]) -> str:
    """Generate Mermaid flowchart syntax for the org DAG (active agents only)."""
    active = [a for a in agents if a.status != "fired"]
    if not active:
        return ""
    lines = ["flowchart TD"]
    for a in active:
        title = a.title.replace('"', "'")
        name = a.name.replace('"', "'")
        lines.append(f'  A{a.id}["{title}\\n{name}"]')
    for a in active:
        if a.parent_agent_id is not None:
            lines.append(f"  A{a.parent_agent_id} --> A{a.id}")
    for a in active:
        for link in a.extra_manager_links:
            lines.append(f"  A{link.manager_id} --> A{a.id}")
    return "\n".join(lines)


def build_org_tree(agents: list[Agent]) -> TreeNode | None:
    """Builds a tree from a flat, already-loaded list of Agent rows (no further DB access)."""
    nodes = {a.id: TreeNode(a) for a in agents}
    root = None
    for a in agents:
        node = nodes[a.id]
        if a.parent_agent_id is None:
            root = node
        else:
            parent_node = nodes.get(a.parent_agent_id)
            if parent_node:
                parent_node.children.append(node)
    return root
