from dataclasses import dataclass
from typing import Set


@dataclass
class JoinInfo:
    """Contains information about a join operation"""
    left_tables: Set[str]
    right_tables: Set[str]
    condition: str
    join_type: str