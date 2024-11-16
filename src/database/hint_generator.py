from collections.abc import Hashable
from typing import Dict, Set, List, Tuple
import networkx as nx
import re

from src.custom_types.qep_types import JoinType, ScanType


class HintConstructor:
    def __init__(self, graph: nx.DiGraph, alias_map):
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
        self.alias_map = alias_map # Will store table_name: alias mappings
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

    @staticmethod
    def _find_innermost_parens(s):
        """Find the position of the innermost complete set of parentheses."""
        stack = []
        for i, char in enumerate(s):
            if char == '(':
                stack.append(i)
            elif char == ')':
                start = stack.pop()
                # Check if this is the innermost pair by looking for ( between start and end
                if '(' not in s[start + 1:i]:
                    return start, i
        return None, None

    def _parse_nested_expression(self, expr):
        """Parse nested parentheses expressions like ((((l s) o) c)) into pairs."""

        expr = expr.strip()
        results = []
        working_expr = expr
        last_result = None

        while '(' in working_expr:
            start, end = self._find_innermost_parens(working_expr)
            if start is None:
                break

            # Extract and parse the innermost content
            inner = working_expr[start + 1:end]
            parts = inner.strip().split()

            if len(parts) == 2:
                if last_result is None:
                    # First pair (l s)
                    results.append(f"({parts[0]} and {parts[1]})")
                    last_result = f"({parts[0]} {parts[1]})"
                else:
                    # Following pairs
                    results.append(f"{last_result} and {parts[-1]}")
                    last_result = f"({last_result} {parts[-1]})"

            # Replace the parsed section with a placeholder
            working_expr = working_expr[:start] + "x" + working_expr[end + 1:]

        return results

    def _generate_explain(self, hint_lst: List[str]) -> Dict[str, str]:
        """Generate explanation for each hint."""
        hint_explain_d = {}
        for hint in hint_lst:
            if "Join" or "Nest" in hint:
                # Is Join hint
                _split = hint.split("(")
                join_type = _split[0]
                relations_lst = _split[-1].replace(')', '').split(" ")
                relations_str = " ,".join(relations_lst)
                tables_lst = [self.alias_map[relation] for relation in relations_lst]
                tables_str = " ,".join(tables_lst)
                hint_explanation = f"This hint specifies that the optimizer should use a {join_type} on the relations with aliases {relations_str} corresponding to tables {tables_str}."
            elif "LEADING" in hint: # is join order hint
                join_pairs = self._parse_nested_expression(hint)
                first_join_pair = join_pairs[0]
                intermediate_join_pairs = join_pairs[1:-1]
                intermediate_join_pairs = ". ".join(["The next join pair is " + pair for pair in intermediate_join_pairs])
                final_join_pair = join_pairs[-1]
                hint_explanation = f"This hint specifies the join order of the relations in the query plan. The first join pair is {first_join_pair}.{intermediate_join_pairs}. The final join pair is {final_join_pair}."
            else: # is Scan hint
                _split = hint.split("(")
                alias = _split[-1].replace(')', '')
                hint_explanation = f"This hint specifies that the optimizer should use a {_split[0]} on the relation {self.alias_map[alias]} with alias {alias}."
            hint_explain_d[hint] = hint_explanation
        return hint_explain_d

    def generate_hints(self) -> Tuple[str, List[str], Dict[str, str]]:
        """Generate complete hint string."""
        # Generate all hints
        hints = []
        hint_expl_d = {}

        # Add join order hint
        join_order = self._construct_join_order()
        if join_order:
            hints.append(join_order)
            hint_expl_d | self._generate_explain([join_order])

        # Add join type hints
        join_hints = self._get_join_hints()
        if join_hints:
            hints.extend(join_hints)
            hint_expl_d | self._generate_explain(join_hints)

        # Add scan hints
        scan_hints = self._get_scan_hints()
        if scan_hints:
            hints.extend(scan_hints)
            hint_expl_d | self._generate_explain(scan_hints)
            hints.extend(scan_hints)

        # Combine all hints
        return f"/*+ {' '.join(hints)} */", hints, hint_expl_d