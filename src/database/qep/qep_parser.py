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
        self.node_counter = 0
        self.pos = {}
        self.table_references = defaultdict(set)  # Track table references
        self.alias_map = {}  # Map aliases to original table names

    def reset(self):
        """Reset the graph and node counter for a new parsing operation."""
        self.graph = nx.DiGraph()
        self.node_counter = 0
        self.pos = {}
        self.table_references.clear()
        self.alias_map.clear()

    def _extract_tables_from_condition(self, condition: str) -> Set[str]:
        """
        Extract table aliases from a join condition or filter.

        Args:
            condition: The join condition or filter string

        Returns:
            Set of table aliases found in the condition
        """
        tables = set()
        if not condition:
            return tables

        # Split condition into parts
        parts = condition.replace('(', ' ').replace(')', ' ').split()

        # Look for table aliases (typically before dots)
        for part in parts:
            if '.' in part:
                alias = part.split('.')[0]
                # Convert alias to original table name if known
                tables.add(self.alias_map.get(alias, alias))

        return tables

    def _resolve_table_name(self, alias: str) -> str:
        """
        Resolve an alias to its original table name.

        Args:
            alias: The table alias to resolve

        Returns:
            Original table name or the alias if not found
        """
        return self.alias_map.get(alias, alias)

    def _format_table_reference(self, table_name: str, alias: str = None) -> str:
        """
        Format a table reference with its alias if different from the table name.

        Args:
            table_name: Original table name
            alias: Table alias (if any)

        Returns:
            Formatted table reference string
        """
        if alias and alias != table_name:
            return f"{table_name} (as {alias})"
        return table_name

    def _infer_tables_for_node(self, node_data: Dict[str, Any]) -> Set[str]:
        """
        Infer all tables involved in a node's operation.

        Args:
            node_data: Dictionary containing node information

        Returns:
            Set of original table names involved in this node
        """
        tables = set()

        # Direct table reference
        if 'Relation Name' in node_data:
            table_name = node_data['Relation Name']
            alias = node_data.get('Alias', table_name)
            # Store the alias mapping
            self.alias_map[alias] = table_name
            tables.add(table_name)

        # Check various conditions that might reference tables
        conditions = [
            node_data.get('Hash Cond', ''),
            node_data.get('Join Filter', ''),
            node_data.get('Filter', ''),
            node_data.get('Index Cond', ''),
            node_data.get('Recheck Cond', '')
        ]

        for condition in conditions:

            for t in self._extract_tables_from_condition(condition):
                name = self._resolve_table_name(t)

                if name != t: # if alias is successfully resolved to table name
                    tables.add(name) # add table name
                    tables.remove(t) # remove alias

        return tables

    def _get_table_info(self, node_data: Dict[str, Any]) -> str:
        """
        Extract table information from a node.

        Args:
            node_data: Dictionary containing node information

        Returns:
            String containing table information
        """
        table_info = []

        # Check for relation name (direct table scans)
        if 'Relation Name' in node_data:
            table_name = node_data['Relation Name']
            alias = node_data.get('Alias')
            table_info.append(f"Table: {self._format_table_reference(table_name, alias)}")

        # Check for join conditions and resolve aliases in them
        if 'Hash Cond' in node_data:
            cond = node_data['Hash Cond']
            # Replace aliases with table names in condition
            for alias, table in self.alias_map.items():
                cond = cond.replace(f"{alias}.", f"{table}.")
            table_info.append(f"Join: {cond}")
        elif 'Join Filter' in node_data:
            cond = node_data['Join Filter']
            # Replace aliases with table names in condition
            for alias, table in self.alias_map.items():
                cond = cond.replace(f"{alias}.", f"{table}.")
            table_info.append(f"Join: {cond}")

        return '\n'.join(table_info) if table_info else ''

    def _propagate_table_info(self):
        """
        Propagate table information up the tree to identify implicit joins.
        """
        # Process nodes in reverse topological order (bottom-up)
        for node in reversed(list(nx.topological_sort(self.graph))):
            node_tables = set()

            # Get tables from children
            for child in self.graph.successors(node):
                node_tables.update(self.table_references[child])

            # Add this node's own tables
            node_tables.update(self.table_references[node])

            # Update the node's table references
            self.table_references[node] = node_tables

            # Update node attributes with comprehensive table info
            node_data = self.graph.nodes[node]
            tables_str = ', '.join(sorted(node_tables))
            if tables_str and 'table_info' in node_data:
                current_info = node_data['table_info']
                if not current_info:
                    node_data['table_info'] = f"Tables: {tables_str}"
                elif "Tables:" not in current_info:
                    node_data['table_info'] += f"\nTables: {tables_str}"

            # Store resolved table names in node attributes
            node_data['resolved_tables'] = sorted(node_tables)

    def _parse_node(self, node_data: Dict[str, Any], parent_id: Optional[str] = None) -> str:
        """
        Recursively parse a node and its children.

        Args:
            node_data: Dictionary containing node information
            parent_id: ID of the parent node (if any)

        Returns:
            The ID of the created node
        """
        node_id = str(uuid.uuid4())

        # Extract table information
        table_info = self._get_table_info(node_data)

        # Infer tables involved in this node
        tables = self._infer_tables_for_node(node_data)
        self.table_references[node_id].update(tables)

        # Extract node attributes
        node_attrs = {
            'node_type': node_data.get('Node Type', 'Unknown'),
            'startup_cost': node_data.get('Startup Cost', 0.0),
            'total_cost': node_data.get('Total Cost', 0.0),
            'plan_rows': node_data.get('Plan Rows', 0),
            'plan_width': node_data.get('Plan Width', 0),
            'table_info': table_info,
            'original_tables': tables  # Store the original table names
        }

        # Store all additional attributes from the node data
        for key, value in node_data.items():
            if key not in ['Plans', 'Node Type', 'Startup Cost', 'Total Cost',
                           'Plan Rows', 'Plan Width', 'table_info']:
                node_attrs[key.lower().replace(' ', '_')] = value

        # Add node to graph
        self.graph.add_node(node_id, **node_attrs)

        # If this node has a parent, add the edge
        if parent_id is not None:
            self.graph.add_edge(parent_id, node_id)

        # Recursively process child plans
        if 'Plans' in node_data:
            for child_plan in node_data['Plans']:
                self._parse_node(child_plan, node_id)

        return node_id

    def parse(self, qep_data: List) -> nx.DiGraph:
        """
        Parse the QEP data and return a NetworkX directed graph.

        Args:
            qep_data: The QEP data structure to parse

        Returns:
            A NetworkX directed graph representing the query plan
        """
        self.reset()

        # Parse the QEP structure
        if isinstance(qep_data, list) and len(qep_data) > 0:
            if isinstance(qep_data[0], tuple) and len(qep_data[0]) > 0:
                if isinstance(qep_data[0][0], list) and len(qep_data[0][0]) > 0:
                    root_plan = qep_data[0][0][0].get('Plan', {})
                    self._parse_node(root_plan)

        # After building the tree, propagate table information
        self._propagate_table_info()

        return self.graph

    def get_tree_statistics(self) -> Dict[str, Any]:
        """
        Get basic statistics about the parsed tree.

        Returns:
            Dictionary containing tree statistics
        """
        # Convert all table references to original table names
        all_tables = set()
        for tables in self.table_references.values():
            resolved_tables = {self._resolve_table_name(t) for t in tables}
            all_tables.update(resolved_tables)

        return {
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'depth': max(nx.shortest_path_length(self.graph,
                                                 source=list(nx.topological_sort(self.graph))[0]).values()),
            'node_types': list(set(nx.get_node_attributes(self.graph, 'node_type').values())),
            'total_cost': sum(nx.get_node_attributes(self.graph, 'total_cost').values()),
            'tables_involved': sorted(all_tables),
            'alias_mappings': dict(self.alias_map)
        }

    def get_tree(self) -> nx.DiGraph:
        return self.graph

if __name__ == "__main__":
    db_manager = DatabaseManager('TPC-H')
    #res = db_manager.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
    res = db_manager.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
    q = QEPParser()
    tree = q.parse(res)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    QEPVisualizer(tree).visualize(VIZ_DIR / "qep_tree.png")
    #q.visualize(VIZ_DIR / "qep_tree.png")