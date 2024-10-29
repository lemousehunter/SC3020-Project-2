from dataclasses import dataclass
from typing import Set, Dict, List
import networkx as nx
from enum import Enum, auto

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_visualizer import QEPVisualizer
from src.settings.filepaths import VIZ_DIR


class NodeType(Enum):
    SCAN = auto()
    JOIN = auto()


class ScanType(Enum):
    SEQ_SCAN = "Seq Scan"
    INDEX_SCAN = "Index Scan"
    INDEX_ONLY_SCAN = "Index Only Scan"
    BITMAP_HEAP_SCAN = "Bitmap Heap Scan"
    BITMAP_INDEX_SCAN = "Bitmap Index Scan"


class JoinType(Enum):
    NESTED_LOOP = "Nested Loop"
    HASH_JOIN = "Hash Join"
    MERGE_JOIN = "Merge Join"


@dataclass
class QueryModification:
    node_type: NodeType
    original_type: str  # Original scan or join type
    new_type: str  # New scan or join type
    tables: Set[str]  # Single table for scan, two tables for join

    def __post_init__(self):
        # Validate tables count based on node type
        if self.node_type == NodeType.SCAN and len(self.tables) != 1:
            raise ValueError("Scan modifications must specify exactly one table")
        if self.node_type == NodeType.JOIN and len(self.tables) != 2:
            raise ValueError("Join modifications must specify exactly two tables")


class QueryModifier:
    def __init__(self, graph: nx.DiGraph):
        """
        Initialize the QueryModifier with a query execution plan graph.

        Args:
            graph: NetworkX DiGraph representing the query execution plan
        """
        self.graph = graph.copy()  # Create a copy to preserve the original
        self.modifications: List[QueryModification] = []

    def add_modification(self, modification: QueryModification):
        """
        Add a modification to be applied to the query plan.

        Args:
            modification: QueryModification object specifying the desired change
        """
        self.modifications.append(modification)

    def _find_matching_nodes(self, modification: QueryModification) -> List[str]:
        """
        Find nodes in the graph that match the modification criteria.

        Args:
            modification: QueryModification object containing search criteria

        Returns:
            List of node IDs that match the criteria
        """
        matching_nodes = []

        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get('node_type', '')

            # Check if this is a scan modification
            if modification.node_type == NodeType.SCAN:
                if (node_type == modification.original_type and
                        'original_tables' in data and
                        len(data['original_tables']) == 1 and
                        data['original_tables'].issubset(modification.tables)):
                    matching_nodes.append(node_id)

            # Check if this is a join modification
            elif modification.node_type == NodeType.JOIN:
                if (node_type == modification.original_type and
                        'original_tables' in data and
                        len(set(data['original_tables']).difference(set(modification.tables))) == 0):
                    matching_nodes.append(node_id)

        return matching_nodes

    def clear_costs(self):
        """
        Clear all cost-related attributes in the graph by setting them to -1.
        This includes startup_cost, total_cost, plan_rows, and plan_width.
        """
        cost_attributes = ['startup_cost', 'total_cost', 'plan_rows', 'plan_width']

        for node_id in self.graph.nodes():
            for attr in cost_attributes:
                if attr in self.graph.nodes[node_id]:
                    self.graph.nodes[node_id][attr] = -1

    def _update_node_attributes(self, node_id: str, modification: QueryModification):
        """
        Update the attributes of a node based on the modification.

        Args:
            node_id: ID of the node to modify
            modification: QueryModification object containing the new attributes
        """
        # Update the node type
        self.graph.nodes[node_id]['node_type'] = modification.new_type

        # Update any type-specific attributes
        if modification.node_type == NodeType.SCAN:
            if modification.new_type == ScanType.INDEX_SCAN.value:
                # Add placeholder index scan attributes
                self.graph.nodes[node_id]['index_name'] = f"idx_{next(iter(modification.tables))}"
                self.graph.nodes[node_id]['scan_direction'] = "Forward"
            elif modification.new_type == ScanType.BITMAP_HEAP_SCAN.value:
                # Remove any index-specific attributes
                self.graph.nodes[node_id].pop('index_name', None)
                self.graph.nodes[node_id].pop('scan_direction', None)

        elif modification.node_type == NodeType.JOIN:
            if modification.new_type == JoinType.HASH_JOIN.value:
                # Add hash join specific attributes
                self.graph.nodes[node_id][
                    'hash_cond'] = f"{next(iter(modification.tables))}.id = {next(iter(modification.tables - {next(iter(modification.tables))}))}.id"
            elif modification.new_type == JoinType.MERGE_JOIN.value:
                # Add merge join specific attributes
                self.graph.nodes[node_id].pop('hash_cond', None)
                self.graph.nodes[node_id][
                    'merge_cond'] = f"{next(iter(modification.tables))}.id = {next(iter(modification.tables - {next(iter(modification.tables))}))}.id"

    def apply_modifications(self) -> nx.DiGraph:
        """
        Apply all stored modifications to the query plan graph.

        Returns:
            Modified NetworkX DiGraph
        """
        for modification in self.modifications:
            matching_nodes = self._find_matching_nodes(modification)

            #print(f"modifications: {modification}", matching_nodes)

            for node_id in matching_nodes:
                self._update_node_attributes(node_id, modification)
        self.clear_costs()
        return self.graph

    def reset(self):
        """
        Reset the graph to its original state and clear modifications.
        """
        self.modifications.clear()

    def get_modified_graph(self) -> nx.DiGraph:
        """
        Get the current state of the modified graph.

        Returns:
            Current state of the modified NetworkX DiGraph
        """
        return self.graph

    def get_modifications_summary(self) -> List[Dict]:
        """
        Get a summary of all modifications made to the graph.

        Returns:
            List of dictionaries containing modification details
        """
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
        SELECT c_name, o_orderdate
        FROM customer c, orders o
        WHERE c.c_custkey = o.o_custkey
        AND c_acctbal > 1000;
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
        new_type=ScanType.INDEX_SCAN.value,
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
