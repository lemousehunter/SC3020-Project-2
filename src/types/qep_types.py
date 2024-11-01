from dataclasses import dataclass
from enum import Enum, auto
from typing import Set, Optional


class NodeType(Enum):
    SCAN = auto()
    JOIN = auto()


class ScanType(Enum):
    SEQ_SCAN = "Seq Scan"
    INDEX_SCAN = "Index Scan"
    INDEX_ONLY_SCAN = "Index Only Scan"
    BITMAP_HEAP_SCAN = "Bitmap Heap Scan"
    BITMAP_INDEX_SCAN = "Bitmap Index Scan"


class JoinType(Enum):
    NESTED_LOOP = "Nested Loop"
    HASH_JOIN = "Hash Join"
    MERGE_JOIN = "Merge Join"


@dataclass
class QEPModification:
    node_type: NodeType
    original_type: str  # Original scan or join type
    new_type: str  # New scan or join type
    tables: Set[str]  # Single table for scan, two tables for join
    node_id: str      # unique node id to identify the node in the QEP

    def __post_init__(self):
        # Validate tables count based on node type
        if self.node_type == NodeType.SCAN and len(self.tables) != 1:
            raise ValueError("Scan modifications must specify exactly one table")
        if self.node_type == NodeType.JOIN and len(self.tables) < 2:
            raise ValueError("Join modifications must specify 2 or more tables")


@dataclass
class SwapNodeIdentifier:
    """Identifies a node either by ID or by type and tables."""
    node_id: Optional[str] = None  # Direct node ID if available
    node_type: Optional[str] = None  # Node type (e.g., "Hash Join", "Merge Join")
    tables: Optional[Set[str]] = None  # Set of tables involved in the node

    def __post_init__(self):
        if self.node_id is None and (self.node_type is None or self.tables is None):
            raise ValueError("Must provide either node_id or both node_type and tables")
        if self.tables is not None:
            self.tables = set(self.tables)  # Ensure tables is a set


@dataclass
class SwapModification:
    """Represents a modification to swap two nodes in the QEP."""
    node1: SwapNodeIdentifier
    node2: SwapNodeIdentifier
