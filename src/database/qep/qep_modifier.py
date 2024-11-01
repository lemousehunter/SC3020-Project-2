import uuid
from dataclasses import dataclass
from typing import Set, Dict, List, Optional
import networkx as nx
from enum import Enum, auto

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_visualizer import QEPVisualizer
from src.types.qep_types import JoinInfo, NodeType, ScanType, JoinType, QueryModification
from src.settings.filepaths import VIZ_DIR


class QEPModifier:
    def __init__(self, graph: nx.DiGraph):
        """
        Initialize the QueryModifier with a query execution plan graph.

        Args:
            graph: NetworkX DiGraph representing the simplified query execution plan
        """
        self.graph = graph.copy()  # Create a copy to preserve the original
        self.modifications: List[QueryModification] = []

    def _find_matching_nodes(self, modification: QueryModification) -> List[str]:
        """
        Find nodes in the graph that match the modification criteria.

        Args:
            modification: QueryModification object containing the criteria

        Returns:
            List of matching node IDs
        """
        matching_nodes = []

        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get('node_type', '')
            node_tables = set(data.get('tables', []))

            # Check if node matches modification criteria
            if modification.node_type == NodeType.SCAN:
                # For scan nodes, check if it's a scan on the specified table
                if (node_type == modification.original_type and
                        node_tables == modification.tables):
                    matching_nodes.append(node_id)

            elif modification.node_type == NodeType.JOIN:
                #print("mod node type:", modification.node_type)
                # For join nodes, check if it involves the specified tables
                if (node_type == modification.original_type and
                        node_tables == modification.tables):
                    matching_nodes.append(node_id)

        return matching_nodes

    def _update_node_type(self, node_id: str, new_type: str):
        """
        Update the type of a node.

        Args:
            node_id: ID of the node to modify
            new_type: New type to assign to the node
        """
        self.graph.nodes[node_id]['node_type'] = new_type

    def add_modification(self, modification: QueryModification):
        """
        Add a modification to be applied to the query plan.

        Args:
            modification: QueryModification object describing the change
        """
        self.modifications.append(modification)

    def clear_costs(self):
        """Set the cost of all nodes to -1."""
        for node_id in self.graph.nodes():
            self.graph.nodes[node_id]['cost'] = -1

    def apply_modifications(self) -> nx.DiGraph:
        """
        Apply all stored modifications to the query plan graph.

        Returns:
            Modified NetworkX DiGraph
        """
        if not self.modifications:
            pass
            #raise ValueError("No modifications have been added")
        else:

            for modification in self.modifications:
                matching_nodes = self._find_matching_nodes(modification)
                for node_id in matching_nodes:
                    self._update_node_type(node_id, modification.new_type)

            # Clear costs after applying modifications
        self.clear_costs()
        return self.graph

    def reset(self):
        """Reset modifications list."""
        self.modifications.clear()

    def print_modifications(self):
        """Print all pending modifications."""
        print("\nPending Modifications:")
        print("=" * 50)
        for i, mod in enumerate(self.modifications, 1):
            print(f"\nModification {i}:")
            print(f"Node Type: {mod.node_type.value}")
            print(f"Original Type: {mod.original_type}")
            print(f"New Type: {mod.new_type}")
            print(f"Tables: {', '.join(sorted(mod.tables))}")


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
        new_type=ScanType.BITMAP_HEAP_SCAN.value,
        tables={'customer'}
    )

    # Change the nested loop join to a hash join
    join_modification = QueryModification(
        node_type=NodeType.JOIN,
        original_type=JoinType.HASH_JOIN.value,
        new_type=JoinType.NESTED_LOOP.value,
        tables={'customer', 'orders', "lineitem", "supplier"}
    )

    # 4. Apply modifications
    modifier = QEPModifier(original_graph)
    modifier.add_modification(scan_modification)
    modifier.add_modification(join_modification)

    modified_graph = modifier.apply_modifications()

    # 5. Visualize the modified graph
    visualizer = QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_qep_tree.png")
