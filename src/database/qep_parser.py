import networkx as nx
from typing import Dict, Any, Optional, List, Tuple, Set
import uuid
import matplotlib.pyplot as plt
from collections import defaultdict

from src.database.databaseManager import DatabaseManager
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


            #tables.update(resolved_tables)

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

    def _calculate_layout(self, root, width=1., height=1.):
        """
        Create a hierarchical layout with equidistant children and centered parents.

        Args:
            root: Root node of the tree
            width: Horizontal space between sibling nodes
            height: Vertical space between levels

        Returns:
            Dictionary of node positions
        """

        def _get_tree_size(node, seen=None):
            """Calculate the number of leaf nodes in the subtree."""
            if seen is None:
                seen = set()

            if node in seen:
                return 0

            seen.add(node)
            children = list(self.graph.neighbors(node))

            if not children:
                return 1

            return sum(_get_tree_size(child, seen) for child in children)

        def _assign_initial_positions(node, x=0, level=0, seen=None):
            """Assign initial x positions to all nodes."""
            if seen is None:
                seen = set()

            if node in seen:
                return x

            seen.add(node)
            children = list(self.graph.neighbors(node))

            # For leaf nodes, just place them sequentially
            if not children:
                pos[node] = (x, -level)
                return x + width

            # Process children first
            start_x = x
            for child in children:
                if child not in seen:
                    x = _assign_initial_positions(child, x, level + 1, seen)

            # Center parent above its children
            if children:
                children_x = [pos[child][0] for child in children]
                pos[node] = (sum(children_x) / len(children), -level)
            else:
                pos[node] = (x, -level)

            return x

        def _adjust_subtrees(node, seen=None):
            """Adjust subtrees to maintain minimum distance."""
            if seen is None:
                seen = set()

            if node in seen:
                return

            seen.add(node)
            children = list(self.graph.neighbors(node))

            # Process all children first
            for child in children:
                _adjust_subtrees(child, seen)

            # If node has children, ensure they're properly spaced
            if len(children) > 1:
                # Sort children by x position
                children.sort(key=lambda n: pos[n][0])

                # Ensure minimum spacing between adjacent children
                for i in range(1, len(children)):
                    left_child = children[i - 1]
                    right_child = children[i]
                    min_spacing = width * (_get_tree_size(left_child, set()) +
                                           _get_tree_size(right_child, set())) / 2

                    actual_spacing = pos[right_child][0] - pos[left_child][0]

                    if actual_spacing < min_spacing:
                        # Move right subtree
                        delta = min_spacing - actual_spacing
                        for n, (x, y) in pos.items():
                            if x > pos[left_child][0]:
                                pos[n] = (x + delta, y)

                # Center parent above adjusted children positions
                children_x = [pos[child][0] for child in children]
                pos[node] = (sum(children_x) / len(children), pos[node][1])

        # Initialize positions dictionary
        pos = {}

        # First pass: assign initial positions
        _assign_initial_positions(root)

        # Second pass: adjust spacing
        _adjust_subtrees(root)

        # Normalize positions to center the tree
        min_x = min(x for x, y in pos.values())
        max_x = max(x for x, y in pos.values())

        # Scale positions to desired width
        scale = 2.0 / (max_x - min_x) if max_x > min_x else 1
        center_offset = (max_x + min_x) / 2

        # Return normalized and scaled positions
        return {node: ((x - center_offset) * scale, y * height)
                for node, (x, y) in pos.items()}

    def visualize(self, output_file: str = 'qep_tree.png'):
        """
        Visualize the query plan tree using NetworkX and save it to a file.
        Shows only node type, total cost, and involved tables.

        Args:
            output_file: Path where the visualization should be saved
        """
        plt.figure(figsize=(15, 10))

        # Get root node (node with no incoming edges)
        root = [n for n, d in self.graph.in_degree() if d == 0][0]

        # Calculate positions with equidistant children
        pos = self._calculate_layout(root, width=1.0, height=1.0)

        # Draw nodes
        nx.draw_networkx_nodes(self.graph, pos,
                               node_size=3000,
                               node_color='lightblue',
                               node_shape='s')

        # Draw edges
        nx.draw_networkx_edges(self.graph, pos,
                               edge_color='gray',
                               arrows=True,
                               arrowsize=20)

        # Create simplified labels
        labels = {}
        for node, data in self.graph.nodes(data=True):
            label_parts = [
                f"{data['node_type']}",
                f"Cost: {data['total_cost']:.2f}"
            ]

            # Add tables if present in the node's resolved_tables
            if 'resolved_tables' in data and data['resolved_tables']:
                print("data['resolved_tables']:", data['resolved_tables'])
                label_parts.append(f"Tables: {', '.join(data['resolved_tables'])}")
            else:
                if 'original_tables' in data and data['original_tables']:
                    print("data['original_tables']:", data['original_tables'])
                    label_parts.append(f"Tables: {', '.join(data['original_tables'])}")

            labels[node] = '\n'.join(label_parts)

        # Add labels
        nx.draw_networkx_labels(self.graph, pos,
                                labels,
                                font_size=8,
                                verticalalignment='center')

        plt.title('Query Execution Plan Tree')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, bbox_inches='tight', dpi=300)
        plt.close()

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

if __name__ == "__main__":
    db_manager = DatabaseManager('TPC-H')
    res = db_manager.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
    q = QEPParser()
    q.parse(res)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    q.visualize(VIZ_DIR / "qep_tree.png")