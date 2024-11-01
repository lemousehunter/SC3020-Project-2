from typing import Dict, Set, List, Tuple
import networkx as nx
import re


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
        self.processed_tables = set()

    def extract_aliases_from_query(self, query: str) -> Dict[str, str]:
        """Extract table aliases from the query."""
        # Clear existing alias map
        self.alias_map.clear()

        # Look for patterns like "table_name alias" or "table_name AS alias"
        patterns = [
            r'from\s+(\w+)\s+(?:AS\s+)?([A-Za-z]\w*)',  # FROM clause
            r'join\s+(\w+)\s+(?:AS\s+)?([A-Za-z]\w*)',  # JOIN clause
            r',\s*(\w+)\s+(?:AS\s+)?([A-Za-z]\w*)'  # Table lists
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, query, re.IGNORECASE)
            for match in matches:
                table_name, alias = match.groups()
                self.alias_map[table_name.lower()] = alias.lower()

        return self.alias_map

    def _find_root_node(self) -> str:
        """Find the root node of the graph."""
        for node, data in self.graph.nodes(data=True):
            if data.get('is_root', False):
                return node
        return None

    def _find_deepest_rightmost_node(self, start_node: str, visited: Set[str] = None) -> str:
        """Find the deepest rightmost node in the graph starting from given node."""
        if visited is None:
            visited = set()

        if start_node in visited:
            return None

        visited.add(start_node)

        # Get all children (neighbors)
        children = list(self.graph.neighbors(start_node))

        if not children:
            return start_node

        # Recursively check right child first (rightmost path)
        rightmost = self._find_deepest_rightmost_node(children[-1], visited)

        return rightmost

    def _get_node_tables(self, node: str) -> Set[str]:
        """Get the tables involved in a node."""
        return set(self.graph.nodes[node]['tables'])

    def _table_to_alias(self, table: str) -> str:
        """Convert table name to its alias, using lowercase."""
        return self.alias_map.get(table.lower(), table.lower())

    def _build_join_order(self, current_node: str, visited: Set[str]) -> str:
        """
        Recursively build the join order string from bottom up, using aliases.
        Returns the join order string for the current subtree.
        """
        if current_node in visited:
            return ""

        visited.add(current_node)

        # Get children
        children = list(self.graph.neighbors(current_node))

        if not children:
            # Leaf node - get its tables and convert to aliases
            tables = self._get_node_tables(current_node)
            new_tables = tables - self.processed_tables
            if new_tables:
                self.processed_tables.update(new_tables)
                return " ".join(sorted(self._table_to_alias(t) for t in new_tables))
            return ""

        # Process children first (bottom-up)
        left_join = self._build_join_order(children[0], visited) if len(children) > 0 else ""
        right_join = self._build_join_order(children[-1], visited) if len(children) > 1 else ""

        # Get current node's tables
        current_tables = self._get_node_tables(current_node)
        new_tables = current_tables - self.processed_tables

        # Build the join order string using aliases
        if left_join and right_join:
            join_str = f"({left_join} {right_join})"
        elif left_join:
            if new_tables:
                self.processed_tables.update(new_tables)
                new_tables_str = " ".join(sorted(self._table_to_alias(t) for t in new_tables))
                join_str = f"({left_join} {new_tables_str})"
            else:
                join_str = left_join
        elif right_join:
            if new_tables:
                self.processed_tables.update(new_tables)
                new_tables_str = " ".join(sorted(self._table_to_alias(t) for t in new_tables))
                join_str = f"({right_join} {new_tables_str})"
            else:
                join_str = right_join
        else:
            if new_tables:
                self.processed_tables.update(new_tables)
                join_str = " ".join(sorted(self._table_to_alias(t) for t in new_tables))
            else:
                join_str = ""

        return join_str

    def _construct_join_order(self) -> str:
        """Construct the join order hint starting from root to deepest node."""
        # Reset processed tables
        self.processed_tables.clear()

        # Find root node
        root = self._find_root_node()
        if not root:
            return ""

        # Start building join order from root
        join_order = self._build_join_order(root, set())

        if join_order:
            return f"Leading({join_order})"
        return ""

    def _get_scan_hints(self) -> List[str]:
        """Generate scan hints for leaf nodes."""
        scan_hints = []
        for node, data in self.graph.nodes(data=True):
            if 'Scan' in data['node_type'] and not list(self.graph.neighbors(node)):
                scan_type = data['node_type']
                if scan_type in self.scan_hint_map:
                    for table in data['tables']:
                        if table.lower() in self.alias_map:
                            alias = self.alias_map[table.lower()]
                            scan_hint = f"{self.scan_hint_map[scan_type]}({alias})"
                            print("scan_hint:", scan_hint, "data:", data)
                            scan_hints.append(scan_hint)
        return scan_hints

    def _get_join_hints(self) -> List[str]:
        """Generate join hints for all join nodes."""
        join_hints = []
        for node, data in self.graph.nodes(data=True):
            if 'Join' in data['node_type']:
                join_type = data['node_type']
                if join_type in self.join_hint_map:
                    # Get aliases for all tables involved in this join
                    aliases = []
                    for table in data['tables']:
                        if table.lower() in self.alias_map:
                            aliases.append(self.alias_map[table.lower()])
                    if aliases:
                        join_hints.append(f"{self.join_hint_map[join_type]}({' '.join(sorted(aliases))})")
        return join_hints

    def generate_hints(self, query: str) -> str:
        """Generate complete hint string."""
        # First extract aliases from the query
        self.extract_aliases_from_query(query)

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
        return f"/*+ {' '.join(hints)} */"