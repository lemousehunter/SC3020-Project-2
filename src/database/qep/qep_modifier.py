from typing import List
import networkx as nx
from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_visualizer import QEPVisualizer
from src.types.qep_types import ScanType, JoinType, QEPModification
from src.settings.filepaths import VIZ_DIR

from typing import List
import networkx as nx
from src.types.qep_types import NodeType, QEPModification, SwapModification, SwapNodeIdentifier


class QEPModifier:
    def __init__(self, graph: nx.DiGraph):
        """
        Initialize the QueryModifier with a query execution plan graph.

        Args:
            graph: NetworkX DiGraph representing the simplified query execution plan
        """
        self.graph = graph.copy()  # Create a copy to preserve the original
        self.modifications: List[QEPModification | SwapModification] = []

    def _find_matching_nodes(self, modification: QEPModification) -> List[str]:
        """
        Find nodes in the graph that match the modification criteria.

        Args:
            modification: QEPModification object containing the criteria

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
                # For join nodes, check if it involves the specified tables
                if (node_type == modification.original_type and
                        node_tables == modification.tables):
                    matching_nodes.append(node_id)

        return matching_nodes

    def _find_node_by_identifier(self, identifier: SwapNodeIdentifier) -> str:
        """
        Find a node in the graph that matches the given identifier.

        Args:
            identifier: SwapNodeIdentifier containing either node_id or node_type and tables

        Returns:
            Matching node ID or None if not found
        """
        if identifier.node_id is not None:
            if self.graph.has_node(identifier.node_id):
                return identifier.node_id
            return None

        # Search by type and tables
        for node_id, data in self.graph.nodes(data=True):
            if (data.get('node_type') == identifier.node_type and
                    set(data.get('tables', [])) == identifier.tables):
                return node_id
        return None

    def _update_node_type(self, node_id: str, new_type: str):
        """
        Update the type of a node.

        Args:
            node_id: ID of the node to modify
            new_type: New type to assign to the node
        """
        if not self.graph.has_node(node_id):
            raise ValueError(f"Node with ID {node_id} not found in the QEP Tree")
        self.graph.nodes[node_id]['node_type'] = new_type

    def _swap_nodes(self, node1_id: str, node2_id: str) -> bool:
        """
        Swap two nodes in the QEP tree while precisely preserving subtree structure and left/right ordering.
        Updates table information for all affected nodes after swapping.

        Args:
            node1_id: ID of first node to swap
            node2_id: ID of second node to swap

        Returns:
            bool: True if swap was successful, False otherwise
        """
        if not self.graph.has_node(node1_id) or not self.graph.has_node(node2_id):
            return False

        # Store the complete state before modification
        node1_parents = list(self.graph.predecessors(node1_id))
        node2_parents = list(self.graph.predecessors(node2_id))

        # For each parent, store the exact order of its children
        parent_children_order = {}

        # Store child order for node1's parents
        for parent in node1_parents:
            parent_children_order[parent] = list(self.graph.successors(parent))

        # Store child order for node2's parents
        for parent in node2_parents:
            if parent not in parent_children_order:  # Avoid overwriting if already stored
                parent_children_order[parent] = list(self.graph.successors(parent))

        # Store direct children of both nodes
        node1_children = list(self.graph.successors(node1_id))
        node2_children = list(self.graph.successors(node2_id))

        # Swap root status if necessary
        node1_is_root = self.graph.nodes[node1_id].get('is_root', False)
        node2_is_root = self.graph.nodes[node2_id].get('is_root', False)
        self.graph.nodes[node1_id]['is_root'] = node2_is_root
        self.graph.nodes[node2_id]['is_root'] = node1_is_root

        # Remove all relevant edges
        edges_to_remove = []
        for parent in node1_parents:
            edges_to_remove.append((parent, node1_id))
        for parent in node2_parents:
            edges_to_remove.append((parent, node2_id))
        for child in node1_children:
            edges_to_remove.append((node1_id, child))
        for child in node2_children:
            edges_to_remove.append((node2_id, child))
        self.graph.remove_edges_from(edges_to_remove)

        # Helper function to add node as child while preserving order
        def add_node_preserving_order(parent_id: str, old_node: str, new_node: str):
            if parent_id not in parent_children_order:
                self.graph.add_edge(parent_id, new_node)
                return

            children = parent_children_order[parent_id]
            old_index = children.index(old_node)

            # Remove all existing edges from this parent
            existing_children = list(self.graph.successors(parent_id))
            for child in existing_children:
                self.graph.remove_edge(parent_id, child)

            # Reconstruct edges in correct order
            for i, child in enumerate(children):
                if i == old_index:
                    self.graph.add_edge(parent_id, new_node)
                elif child != old_node:
                    self.graph.add_edge(parent_id, child)

        # Re-add edges with nodes swapped
        # 1. Connect parents to swapped nodes
        for parent in node1_parents:
            add_node_preserving_order(parent, node1_id, node2_id)

        for parent in node2_parents:
            add_node_preserving_order(parent, node2_id, node1_id)

        # 2. Connect swapped nodes to their new children
        # Node2 gets node1's children
        for child in node1_children:
            if child != node2_id:  # Avoid self-loops
                self.graph.add_edge(node2_id, child)

        # Node1 gets node2's children
        for child in node2_children:
            if child != node1_id:  # Avoid self-loops
                self.graph.add_edge(node1_id, child)

        # Update tables for all nodes after swapping
        def update_node_tables(node_id: str, visited: set = None) -> set:
            """
            Recursively update tables for a node and its children.
            Returns the set of all tables used in this subtree.
            """
            if visited is None:
                visited = set()

            if node_id in visited:
                return set()

            visited.add(node_id)

            # Get all child tables
            tables = set()
            for child in self.graph.successors(node_id):
                child_tables = update_node_tables(child, visited)
                tables.update(child_tables)

            # For leaf nodes (scan nodes), keep their original tables
            node_data = self.graph.nodes[node_id]
            if 'Scan' in node_data['node_type']:
                node_tables = set(node_data['tables'])
                tables.update(node_tables)
            else:
                # For non-leaf nodes, update tables based on children
                node_data['tables'] = list(tables)

            return tables

        # Start table updates from root node
        root_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('is_root', False)]
        if root_nodes:
            update_node_tables(root_nodes[0])

        return True

    def add_modification(self, modification: QEPModification | SwapModification):
        """
        Add a modification to be applied to the query plan.

        Args:
            modification: QEPModification or SwapModification object describing the change
        """
        self.modifications.append(modification)

    def clear_costs(self):
        """Set the cost of all nodes to -1."""
        for node_id in self.graph.nodes():
            self.graph.nodes[node_id]['cost'] = -1

    def apply_modifications(self, match_node_by_id: bool = True) -> nx.DiGraph:
        """
        Apply all stored modifications to the query plan graph.

        Args:
            match_node_by_id: Whether to match nodes by ID (True) or by type and tables (False)

        Returns:
            Modified NetworkX DiGraph
        """
        if not self.modifications:
            return self.graph

        for modification in self.modifications:
            if isinstance(modification, SwapModification):
                # Handle swap modification
                node1_id = self._find_node_by_identifier(modification.node1)
                node2_id = self._find_node_by_identifier(modification.node2)

                if node1_id is None or node2_id is None:
                    raise ValueError("One or both nodes for swap not found in the graph, Node1: ", node1_id, " Node2: ", node2_id)

                self._swap_nodes(node1_id, node2_id)
            else:
                # Handle regular QEPModification
                if match_node_by_id:
                    self._update_node_type(modification.node_id, modification.new_type)
                else:
                    matching_nodes = self._find_matching_nodes(modification)
                    for node_id in matching_nodes:
                        self._update_node_type(node_id, modification.new_type)
            print("Processed modification:", modification)

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
            if isinstance(mod, SwapModification):
                print("Type: Swap")
                print("Node 1:")
                print(f"  ID: {mod.node1.node_id}")
                print(f"  Type: {mod.node1.node_type}")
                print(f"  Tables: {', '.join(sorted(mod.node1.tables)) if mod.node1.tables else 'None'}")
                print("Node 2:")
                print(f"  ID: {mod.node2.node_id}")
                print(f"  Type: {mod.node2.node_type}")
                print(f"  Tables: {', '.join(sorted(mod.node2.tables)) if mod.node2.tables else 'None'}")
            else:
                print(f"Type: {mod.node_type.value}")
                print(f"Original Type: {mod.original_type}")
                print(f"New Type: {mod.new_type}")
                print(f"Tables: {', '.join(sorted(mod.tables))}")


if __name__ == "__main__":
    # 1. Set up the database and get the original query plan
    db_manager = DatabaseManager('TPC-H')
    query = """
        select * 
from customer C, orders O, lineitem L, supplier S
where C.c_custkey = O.o_custkey 
  and O.o_orderkey = L.l_orderkey
  and L.l_suppkey = S.s_suppkey
  and L.l_quantity > (
    select avg(L2.l_quantity) 
    from lineitem L2 
    where L2.l_suppkey = S.s_suppkey
  )
        """

    qep_data = db_manager.get_qep(query)

    # 2. Parse the original plan
    parser = QEPParser()
    original_graph = parser.parse(qep_data)
    parser.print_nodes()

    # 3. Create modifications
    # Change the sequential scan on customer table to an index scan
    scan_modification = QEPModification(
        node_type=NodeType.SCAN,
        original_type=ScanType.SEQ_SCAN.value,
        new_type=ScanType.BITMAP_HEAP_SCAN.value,
        tables={'customer'},
        node_id="SOMESTRING"
    )

    # Change the nested loop join to a hash join
    join_modification = QEPModification(
        node_type=NodeType.JOIN,
        original_type=JoinType.HASH_JOIN.value,
        new_type=JoinType.NESTED_LOOP.value,
        tables={'customer', 'orders', "lineitem", "supplier"},
        node_id = "SOMESTRING"
    )

    swap_mod = SwapModification(
        node1=SwapNodeIdentifier(node_type=JoinType.NESTED_LOOP.value, tables={'supplier', 'orders', 'customer', 'lineitem'}),
        node2=SwapNodeIdentifier(node_type=JoinType.HASH_JOIN.value, tables={'lineitem', 'supplier'})
    )

    # 4. Apply modifications
    modifier = QEPModifier(original_graph)
    modifier.add_modification(scan_modification)
    modifier.add_modification(join_modification)
    modifier.add_modification(swap_mod)

    modified_graph = modifier.apply_modifications(False)

    # 5. Visualize the modified graph
    visualizer = QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_qep_tree.png")
