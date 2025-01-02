"""Base test classes and utilities for graph tests"""

from pydantic import ConfigDict, Field

from lionagi._errors import RelationError
from lionagi.protocols.types import Edge, Graph, Node


class TestNode(Node):
    """Test node class for graph testing"""

    relations: dict = Field(
        default_factory=lambda: {"in": [], "out": []},
        description="Node relations for testing",
    )

    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
    )

    def add_relation(self, edge, direction: str) -> None:
        """Add a relation to the node"""
        if direction not in ["in", "out"]:
            raise ValueError("Direction must be 'in' or 'out'")
        if edge not in self.relations[direction]:
            self.relations[direction].append(edge)

    def remove_relation(self, edge, direction: str) -> None:
        """Remove a relation from the node"""
        if direction not in ["in", "out"]:
            raise ValueError("Direction must be 'in' or 'out'")
        if edge in self.relations[direction]:
            self.relations[direction].remove(edge)


def create_test_node(name: str) -> TestNode:
    """Helper function to create a test node with name"""
    node = TestNode()
    if node.content is None:
        node.content = {}
    node.content["name"] = name
    return node
