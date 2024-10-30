import uuid
from dataclasses import dataclass
from typing import Set, Dict, List, Optional
import networkx as nx
from enum import Enum, auto

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_visualizer import QEPVisualizer
from src.types.qep import JoinInfo, NodeType, ScanType, JoinType, QueryModification
from src.settings.filepaths import VIZ_DIR


class QueryModifier:
    def __init__(self, graph: nx.DiGraph):
        """
        Initialize the QueryModifier with a query execution plan graph.

        Args:
            graph: NetworkX DiGraph representing the query execution plan
        """
        self.graph = graph.copy()  # Create a copy to preserve the original
        self.modifications: List[QueryModification] = []

    def _update_node_attributes(self, node_id: str, modification: QueryModification):
        """
        Update the attributes of a node based on the modification.

        Args:
            node_id: ID of the node to modify
            modification: QueryModification object containing the new attributes
        """
        # Update the node type
        self.graph.nodes[node_id]['node_type'] = modification.new_type

        if modification.node_type == NodeType.SCAN:
            if modification.new_type == ScanType.INDEX_SCAN.value:
                # Add placeholder index scan attributes
                self.graph.nodes[node_id]['index_name'] = f"idx_{next(iter(modification.tables))}"
                self.graph.nodes[node_id]['scan_direction'] = "Forward"
            elif modification.new_type == ScanType.BITMAP_INDEX_SCAN.value:
                # Remove any index-specific attributes
                self.graph.nodes[node_id].pop('index_name', None)
                self.graph.nodes[node_id].pop('scan_direction', None)
                # Create a new Bitmap Index Scan node
                bitmap_index_node_id = str(uuid.uuid4())
                self.graph.add_node(
                    bitmap_index_node_id,
                    node_type=ScanType.BITMAP_INDEX_SCAN.value,
                    original_tables=modification.tables,
                    index_name=f"idx_{next(iter(modification.tables))}_btree"
                )

                # Convert the original node to Bitmap Heap Scan
                self.graph.nodes[node_id]['node_type'] = ScanType.BITMAP_HEAP_SCAN.value

                # Add edge from heap scan to index scan
                self.graph.add_edge(node_id, bitmap_index_node_id)

        elif modification.node_type == NodeType.JOIN:
            # Get child nodes to determine left and right tables
            children = list(self.graph.successors(node_id))
            if len(children) == 2:
                # Store the original tables information
                self.graph.nodes[node_id]['original_tables'] = modification.tables

                # Get tables from children
                left_child = children[0]
                right_child = children[1]

                # Extract tables from child nodes
                left_tables = set(self.graph.nodes[left_child].get('original_tables', set()))
                right_tables = set(self.graph.nodes[right_child].get('original_tables', set()))

                # Store these for reference
                self.graph.nodes[node_id]['left_tables'] = left_tables
                self.graph.nodes[node_id]['right_tables'] = right_tables

                # Determine table names for join condition
                left_table = 'customer' if 'customer' in left_tables else 'orders'
                right_table = 'orders' if 'orders' in right_tables else 'customer'

                if modification.new_type == JoinType.HASH_JOIN.value:
                    # Add hash join specific attributes
                    self.graph.nodes[node_id]['hash_cond'] = f"({left_table}.c_custkey = {right_table}.o_custkey)"
                    # Clean up any merge-specific attributes
                    self.graph.nodes[node_id].pop('merge_cond', None)

                elif modification.new_type == JoinType.MERGE_JOIN.value:
                    # Add merge join specific attributes
                    self.graph.nodes[node_id].pop('hash_cond', None)
                    self.graph.nodes[node_id]['merge_cond'] = f"({left_table}.c_custkey = {right_table}.o_custkey)"

    def _get_join_info(self, node_id: str) -> Optional[JoinInfo]:
        """
        Extract join information from a join node.
        Handles intermediate nodes like Hash nodes properly.
        """
        node_data = self.graph.nodes[node_id]
        if 'node_type' not in node_data or not node_data['node_type'].endswith('Join'):
            return None

        # Get child nodes
        children = list(self.graph.successors(node_id))
        if len(children) != 2:
            return None

        # Function to get tables from a node and its descendants
        def get_tables_from_subtree(node: str) -> Set[str]:
            node_tables = set(self.graph.nodes[node].get('original_tables', set()))
            if not node_tables:
                # If no tables at this node, check children
                for child in self.graph.successors(node):
                    node_tables.update(get_tables_from_subtree(child))
            return node_tables

        # Get tables from each side of the join
        left_tables = get_tables_from_subtree(children[0])
        right_tables = get_tables_from_subtree(children[1])

        # Extract join condition
        join_cond = None
        if 'hash_cond' in node_data:
            join_cond = node_data['hash_cond']
        elif 'merge_cond' in node_data:
            join_cond = node_data['merge_cond']
        elif 'join_filter' in node_data:
            join_cond = node_data['join_filter']

        # If no explicit join condition, try to construct one
        if not join_cond and left_tables and right_tables:
            try:
                left_table = next(iter(left_tables))
                right_table = next(iter(right_tables))
                if left_table == 'orders' and right_table == 'customer':
                    join_cond = f"{left_table}.o_custkey = {right_table}.c_custkey"
                elif left_table == 'customer' and right_table == 'orders':
                    join_cond = f"{left_table}.c_custkey = {right_table}.o_custkey"
                else:
                    left_col, right_col = self._get_join_columns(left_table, right_table)
                    join_cond = f"{left_table}.{left_col} = {right_table}.{right_col}"
            except (StopIteration, ValueError):
                # If we can't construct a join condition, use a default one
                pass

        return JoinInfo(
            left_tables=left_tables,
            right_tables=right_tables,
            condition=join_cond,
            join_type=node_data['node_type']
        )

    def _find_matching_nodes(self, modification: QueryModification) -> List[str]:
        """
        Find nodes in the graph that match the modification criteria.
        """
        matching_nodes = []

        print(f"\nDebug - Looking for nodes to modify:")
        print(f"Modification type: {modification.node_type}")
        print(f"Original type: {modification.original_type}")
        print(f"New type: {modification.new_type}")
        print(f"Tables: {modification.tables}")

        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get('node_type', '')
            print(f"\nNode {node_id}:")
            print(f"Node type: {node_type}")
            print(f"Original tables: {data.get('original_tables', 'None')}")

            # Check if this is a scan modification
            if modification.node_type == NodeType.SCAN:
                if (node_type in ['Seq Scan', 'Sequential Scan'] and
                        'original_tables' in data and
                        len(data['original_tables']) == 1 and
                        data['original_tables'].issubset(modification.tables)):
                    matching_nodes.append(node_id)

                elif (node_type == modification.original_type and
                        'original_tables' in data and
                        len(data['original_tables']) == 1 and
                        data['original_tables'].issubset(modification.tables)):
                    print("Found matching scan node!")
                    matching_nodes.append(node_id)
                    # For join modifications
            elif modification.node_type == NodeType.JOIN:
                if node_type == modification.original_type:
                    # Get tables from both sides of the join
                    join_info = self._get_join_info(node_id)
                    if join_info and join_info.left_tables and join_info.right_tables:
                        all_tables = join_info.left_tables | join_info.right_tables
                        if all_tables == modification.tables:
                            matching_nodes.append(node_id)

        return matching_nodes

    def clear_costs(self):
        """Clear all cost-related attributes in the graph."""
        cost_attributes = ['startup_cost', 'total_cost', 'plan_rows', 'plan_width']
        for node_id in self.graph.nodes():
            for attr in cost_attributes:
                if attr in self.graph.nodes[node_id]:
                    self.graph.nodes[node_id][attr] = -1

    def apply_modifications(self) -> nx.DiGraph:
        """
        Apply all stored modifications to the query plan graph.

        Returns:
            Modified NetworkX DiGraph
        """
        if not self.modifications:
            raise ValueError("No modifications have been added")
        for modification in self.modifications:
            matching_nodes = self._find_matching_nodes(modification)
            for node_id in matching_nodes:
                self._update_node_attributes(node_id, modification)
        self.clear_costs()
        return self.graph

    def add_modification(self, modification: QueryModification):
        """Add a modification to be applied to the query plan."""
        self.modifications.append(modification)

    def reset(self):
        """Reset the graph to its original state and clear modifications."""
        self.modifications.clear()

    def get_modified_graph(self) -> nx.DiGraph:
        """Get the current state of the modified graph."""
        return self.graph

    def get_modifications_summary(self) -> List[Dict]:
        """Get a summary of all modifications made to the graph."""
        return [
            {
                'node_type': mod.node_type.name,
                'original_type': mod.original_type,
                'new_type': mod.new_type,
                'tables': list(mod.tables)
            }
            for mod in self.modifications
        ]


if __name__ == "__main__":
    # 1. Set up the database and get the original query plan
    db_manager = DatabaseManager('TPC-H')
    query = """
        select * from customer C, orders O where C.c_custkey = O.o_custkey;
        """

    qep_data = db_manager.get_qep(query)

    # 2. Parse the original plan
    parser = QEPParser()
    original_graph = parser.parse(qep_data)

    # 3. Create modifications
    # Change the sequential scan on customer table to an index scan
    scan_modification = QueryModification(
        node_type=NodeType.SCAN,
        original_type=ScanType.SEQ_SCAN.value,
        new_type=ScanType.BITMAP_INDEX_SCAN.value,
        tables={'customer'}
    )

    # Change the nested loop join to a hash join
    join_modification = QueryModification(
        node_type=NodeType.JOIN,
        original_type=JoinType.HASH_JOIN.value,
        new_type=JoinType.NESTED_LOOP.value,
        tables={'customer', 'orders'}
    )

    # 4. Apply modifications
    modifier = QueryModifier(original_graph)
    modifier.add_modification(scan_modification)
    modifier.add_modification(join_modification)

    modified_graph = modifier.apply_modifications()

    # 5. Visualize the modified graph
    visualizer = QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_qep_tree.png")
