from app.db.models import Agent


class TreeNode:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.children: list["TreeNode"] = []

    @property
    def active_child_count(self) -> int:
        return len([c for c in self.children if c.agent.status != "fired"])


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
