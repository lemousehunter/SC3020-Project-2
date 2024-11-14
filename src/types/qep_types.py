from dataclasses import dataclass
from enum import Enum, auto, EnumMeta
from typing import Set, Tuple


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
class TypeModification:
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
class JoinOrderModificationSpecced:
    # Join order modification with specified join types and orders to identify nodes involved
    join_order_1: Tuple[str, str]
    join_type_1: str
    join_order_2: Tuple[str, str]
    join_type_2: str

    def __post_init__(self):
        # Validate join types:
        if self.join_type_1 not in JoinType:
            if self.join_type_2 not in JoinType:
                raise ValueError(f"Invalid join type: {self.join_type_1} and {self.join_type_2}")
            else:
                raise ValueError(f"Invalid join type: {self.join_type_1}")
        elif self.join_type_2 not in JoinType:
            raise ValueError(f"Invalid join type: {self.join_type_2}")


@dataclass
class JoinOrderModification:
    # Join order modification with node id
    join_node_1_id: str
    join_node_2_id: str


if __name__ == "__main__":
    print("Seq Scan" in NodeType)