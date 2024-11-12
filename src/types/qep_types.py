from dataclasses import dataclass
from enum import Enum, auto, EnumMeta
from typing import Set


class MetaEnum(EnumMeta):
    def __contains__(self, item):
        if item in self.__members__:
            return True
        else:
            # Check in the values of the members
            for member in self.__members__.values():
                if item in member.value:
                    return True
            return False


class BaseEnum(Enum, metaclass=MetaEnum):
    pass


class ScanType(BaseEnum):
    SEQ_SCAN = "Seq Scan"
    INDEX_SCAN = "Index Scan"
    INDEX_ONLY_SCAN = "Index Only Scan"
    BITMAP_HEAP_SCAN = "Bitmap Heap Scan"
    BITMAP_INDEX_SCAN = "Bitmap Index Scan"


class JoinType(BaseEnum):
    NESTED_LOOP = "Nested Loop"
    HASH_JOIN = "Hash Join"
    MERGE_JOIN = "Merge Join"


class NodeType(BaseEnum):
    SCAN = ScanType
    JOIN = JoinType


@dataclass
class QueryModification:
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


if __name__ == "__main__":
    print("Seq Scan" in NodeType)