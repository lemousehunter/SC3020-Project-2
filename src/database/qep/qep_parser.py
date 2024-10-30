import networkx as nx
from typing import Dict, Any, Optional, List, Tuple, Set
import uuid
import matplotlib.pyplot as plt
from collections import defaultdict

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_visualizer import QEPVisualizer
from src.settings.filepaths import VIZ_DIR


class QEPParser:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.alias_map = {}  # Map aliases to original table names

    def reset(self):
        """Reset the parser state."""
        self.graph = nx.DiGraph()
        self.alias_map.clear()

    def _register_alias(self, alias: str, table_name: str):
        """Register a table alias."""
        self.alias_map[alias.lower()] = table_name

    def _resolve_table_name(self, identifier: str) -> str:
        """
        Resolve a table identifier to its full original name.
        Returns the original identifier if no mapping exists.
        """
        return self.alias_map.get(identifier.lower(), identifier)

    def _process_join_condition(self, condition: str) -> set:
        """
        Process a join condition to extract and resolve table names.
        Example: "(c.c_custkey = o.o_custkey)" -> {"customer", "orders"}
        """
        tables = set()
        if not condition:
            return tables

        # Split on comparison operators and other delimiters
        parts = condition.replace('(', ' ').replace(')', ' ').replace('=', ' ').split()

        for part in parts:
            if '.' in part:
                alias = part.split('.')[0].strip()
                resolved = self._resolve_table_name(alias)
                if resolved != alias:  # Only add if we successfully resolved an alias
                    tables.add(resolved)

        return tables

    def _extract_tables(self, node_data: Dict[str, Any]) -> set:
        """Extract and resolve all table names from a node."""
        tables = set()

        # Handle direct table references
        if 'Relation Name' in node_data:
            table_name = node_data['Relation Name']
            alias = node_data.get('Alias', table_name)
            self._register_alias(alias, table_name)
            tables.add(table_name)

        # Process join conditions
        conditions = [
            node_data.get('Hash Cond', ''),
            node_data.get('Join Filter', ''),
            node_data.get('Filter', ''),
            node_data.get('Index Cond', ''),
            node_data.get('Merge Cond', ''),
            node_data.get('Recheck Cond', '')
        ]

        for condition in conditions:
            if condition:
                join_tables = self._process_join_condition(condition)
                tables.update(join_tables)

        return tables

    def _get_child_tables(self, child_nodes: List[str]) -> Set[str]:
        """Collect all tables from child nodes."""
        tables = set()
        for child_id in child_nodes:
            child_tables = self.graph.nodes[child_id].get('tables', set())
            tables.update(child_tables)
        return tables

    def _parse_node(self, node_data: Dict[str, Any], parent_id: Optional[str] = None, is_root: bool = False) -> str:
        """Parse a single node and its children."""
        node_id = str(uuid.uuid4())
        tables = set()

        # Process children first to ensure all aliases are registered
        child_nodes = []
        if 'Plans' in node_data:
            for child_plan in node_data['Plans']:
                child_id = self._parse_node(child_plan, node_id, is_root=False)
                child_nodes.append(child_id)

        # Extract tables from this node
        node_tables = self._extract_tables(node_data)
        tables.update(node_tables)

        # For join nodes, include tables from all children
        node_type = node_data.get('Node Type', '')
        if 'Join' in node_type or node_type in ['Nested Loop']:
            child_tables = self._get_child_tables(child_nodes)
            tables.update(child_tables)
        elif node_type == 'Materialize':
            # For Materialize nodes, propagate tables from child
            child_tables = self._get_child_tables(child_nodes)
            tables.update(child_tables)

        node_attrs = {
            'node_type': node_type,
            'tables': sorted(tables),  # Sort for consistent ordering
            'cost': node_data.get('Total Cost', 0.0),
            'is_root': is_root
        }

        # Add node to graph
        self.graph.add_node(node_id, **node_attrs)

        # Connect to parent if exists
        if parent_id is not None:
            self.graph.add_edge(parent_id, node_id)

        return node_id

    def parse(self, qep_data: List) -> nx.DiGraph:
        """Parse the QEP data into a graph."""
        self.reset()

        if isinstance(qep_data, list) and len(qep_data) > 0:
            if isinstance(qep_data[0], tuple) and len(qep_data[0]) > 0:
                if isinstance(qep_data[0][0], list) and len(qep_data[0][0]) > 0:
                    root_plan = qep_data[0][0][0].get('Plan', {})
                    self._parse_node(root_plan, parent_id=None, is_root=True)

        return self.graph

    def print_nodes(self):
        """Print all nodes and their attributes in a hierarchical format."""
        def get_node_level(node):
            root = [n for n, d in self.graph.nodes(data=True) if d.get('is_root', False)][0]
            try:
                return nx.shortest_path_length(self.graph, root, node)
            except:
                return 0

        nodes = list(self.graph.nodes(data=True))
        nodes.sort(key=lambda x: get_node_level(x[0]))

        print("\nQuery Execution Plan Node Details:")
        print("=" * 50)

        for node_id, attrs in nodes:
            level = get_node_level(node_id)
            indent = "  " * level

            print(f"\n{indent}Node Level {level}:")
            print(f"{indent}{'─' * 20}")
            print(f"{indent}Type: {attrs['node_type']}")
            print(f"{indent}Cost: {attrs['cost']:.2f}")
            print(f"{indent}Tables: {', '.join(attrs['tables']) if attrs['tables'] else 'None'}")
            print(f"{indent}Is Root: {attrs['is_root']}")


if __name__ == "__main__":
    db_manager = DatabaseManager('TPC-H')
    #res = db_manager.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
    res = db_manager.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
    q = QEPParser()
    tree = q.parse(res)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    QEPVisualizer(tree).visualize(VIZ_DIR / "qep_tree.png")
    q.print_nodes()
    #q.visualize(VIZ_DIR / "qep_tree.png")