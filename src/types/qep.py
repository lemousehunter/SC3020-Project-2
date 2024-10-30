from dataclasses import dataclass
from enum import Enum, auto
from typing import Set


@dataclass
class JoinInfo:
    """Contains information about a join operation"""
    left_tables: Set[str]
    right_tables: Set[str]
    condition: str
    join_type: str


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
class QueryModification:
    node_type: NodeType
    original_type: str  # Original scan or join type
    new_type: str  # New scan or join type
    tables: Set[str]  # Single table for scan, two tables for join

    def __post_init__(self):
        # Validate tables count based on node type
        if self.node_type == NodeType.SCAN and len(self.tables) != 1:
            raise ValueError("Scan modifications must specify exactly one table")
        if self.node_type == NodeType.JOIN and len(self.tables) != 2:
            raise ValueError("Join modifications must specify exactly two tables")