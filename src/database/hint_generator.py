from collections.abc import Hashable
from typing import Dict, Set, List, Tuple
import networkx as nx
import re

from src.types.qep_types import JoinType, ScanType


class HintConstructor:
    def __init__(self, graph: nx.DiGraph):
        """Initialize with QEP graph and hint mappings."""
        self.graph = graph
        self.scan_hint_map = {
            'Seq Scan': 'SeqScan',
            'Index Scan': 'IndexScan',
            'Index Only Scan': 'IndexOnlyScan',
            'Bitmap Heap Scan': 'BitmapScan',
            'Tid Scan': 'TidScan'
        }
        self.join_hint_map = {
            'Nested Loop': 'NestLoop',
            'Hash Join': 'HashJoin',
            'Merge Join': 'MergeJoin'
        }
        self.alias_map = {}  # Will store table_name: alias mappings
        self.root = self._get_root()

    def _get_root(self):
        """Get root node of the graph."""
        for node, node_data in self.graph.nodes(True):
            if node_data['is_root']:
                return node

    @staticmethod
    def _format_join_order_str(join_order_str: str):
        return f"({join_order_str.replace('[', '(').replace(']', ')').replace(',', '')})"

    def _construct_join_order(self) -> str:
        """Construct join order hint from root node join_order attribute (str)"""
        join_order_str = self._format_join_order_str(self.graph.nodes[self.root]['join_order'])
        return f'LEADING{join_order_str}'

    def _get_join_hints(self) -> List[str]:
        """Get join type hints from the graph."""
        hints = []
        for node, node_data in self.graph.nodes(data=True):
            join_type = node_data['node_type']
            if join_type in JoinType and join_type != "Hash":
                print("join_type", join_type)
                join_aliases = node_data['_join_table_aliases']
                hints.append(f'{self.join_hint_map[join_type]}({" ".join(join_aliases)})')
        return hints

    def check_subquery(self, node) -> bool:
        """Check if the node is a subquery node based on ancestry"""
        for node in nx.ancestors(self.graph, node):
            if self.graph.nodes[node]['_subplan']:
                return True

    def _get_scan_hints(self) -> List[str]:
        """Get scan type hints from the graph."""
        hints = []
        for node, node_data in self.graph.nodes(data=True):
            # ignore subquery nodes
            if self.check_subquery(node):
                continue
            scan_type = node_data['node_type']
            if scan_type in ScanType:
                scan_table = next(iter(node_data['aliases']))
                hints.append(f'{self.scan_hint_map[scan_type]}({scan_table})')

        return hints

    def generate_hints(self) -> Tuple[str, List[str]]:
        """Generate complete hint string."""
        # Generate all hints
        hints = []

        # Add join order hint
        join_order = self._construct_join_order()
        if join_order:
            hints.append(join_order)

        # Add join type hints
        join_hints = self._get_join_hints()
        hints.extend(join_hints)

        # Add scan hints
        scan_hints = self._get_scan_hints()
        hints.extend(scan_hints)

        # Combine all hints
        return f"/*+ {' '.join(hints)} */", hints