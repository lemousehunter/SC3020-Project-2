from copy import deepcopy
from typing import List, Tuple, Union, Dict
from collections import OrderedDict
import networkx as nx
from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_visualizer import QEPVisualizer
from src.types.qep_types import NodeType, ScanType, JoinType, TypeModification, JoinOrderModification, \
    JoinOrderModificationSpecced
from src.settings.filepaths import VIZ_DIR


class QEPModifier:
    def __init__(self, graph: nx.DiGraph, join_order: List, alias_map: Dict[str, str]):
        """
        Initialize the QueryModifier with a query execution plan graph.

        Args:
            graph: NetworkX DiGraph representing the simplified query execution plan
        """
        self.graph = deepcopy(graph) # Create a copy to preserve the original
        self.modifications: List[Union[TypeModification, JoinOrderModification, JoinOrderModificationSpecced]] = []
        self.join_order = deepcopy(join_order) # Create a copy to preserve the original
        self.alias_map = alias_map

    def _find_matching_nodes(self, modification: TypeModification) -> List[str]:
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


            # Check if node matches modification criteria
            if modification.node_type == NodeType.SCAN:
                # For scan nodes, check if it's a scan on the specified table
                node_table_aliases = set(data.get('aliases', []))
                if (node_type == modification.original_type and
                        len(node_table_aliases.intersection(modification.tables)) == len(modification.tables) ):
                    matching_nodes.append(node_id)

            elif modification.node_type == NodeType.JOIN:
                # print("mod node type:", modification.node_type)
                # For join nodes, check if it involves the specified tables
                node_table_aliases = set(data.get('_join_table_aliases', []))
                print("node_table_aliases:", node_table_aliases)
                if (node_type == modification.original_type and
                        len(node_table_aliases.intersection(modification.tables)) == len(modification.tables)):
                    matching_nodes.append(node_id)

        return matching_nodes

    def _update_node_type(self, node_id: str, new_type: str):
        """
        Update the type of a node.

        Args:
            node_id: ID of the node to modify
            new_type: New type to assign to the node
        """
        if not self.graph.has_node(node_id):
            raise ValueError(f"Node with ID {node_id} not found in the QEP Tree")
        nx.set_node_attributes(self.graph, {node_id: {'node_type': new_type}})

    def add_modification(self, modification: Union[TypeModification, JoinOrderModification, JoinOrderModificationSpecced]):
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

    def _get_join_node_by_type_and_alias(self, join_type: str, join_pair: Tuple[str, str]) -> str:
        """
        Get the join node ID by join type and join pair.

        Args:
            join_type: Join type to match
            join_pair: Pair of table aliases involved in the join
        """
        for node, node_data in self.graph.nodes(data=True):
            if node_data.get('node_type') == join_type:
                print("node_data['join_on']:", node_data['join_on'])
                if node_data['join_on'] == join_pair:
                    return node

    def _find_element(self, nested_list, target, path=None):
        """
        Find the path to a target element in a nested list.
        Returns a list of indices representing the path to the element.
        """
        if path is None:
            path = []

        if not isinstance(nested_list, list):
            return None if nested_list != target else path

        for i, item in enumerate(nested_list):
            current_path = path + [i]
            if item == target:
                return current_path
            if isinstance(item, list):
                result = self._find_element(item, target, current_path)
                if result is not None:
                    return result
        return None

    @staticmethod
    def _get_element_at_path(nested_list, path):
        """Get element at the specified path in nested list."""
        current = nested_list
        for index in path:
            current = current[index]
        return current

    @staticmethod
    def _set_element_at_path(nested_list, path, value):
        """Set element at the specified path in nested list."""
        current = nested_list
        for index in path[:-1]:
            current = current[index]
        current[path[-1]] = value

    def _swap_or_replace_elements(self, nested_list, elem1, elem2):
        """
        If both elements exist in the list, swap them.
        If elem2 doesn't exist, replace elem1 with elem2.
        Returns a new list with the modified elements.
        """
        # Create a deep copy to avoid modifying the original list
        result = deepcopy(list(nested_list))

        # Find path to elem1
        path1 = self._find_element(result, elem1)

        # Find path to elem2
        path2 = self._find_element(result, elem2)

        if path2 is None:
            # If elem2 doesn't exist, simply replace elem1 with elem2
            self._set_element_at_path(result, path1, elem2)
        else:
            # If elem1 doesn't exist, simply replace elem2 with elem1
            if path1 is None:
                self._set_element_at_path(result, path2, elem1)
            else:
                # If both elements exist, swap them
                val1 = self._get_element_at_path(result, path1)
                val2 = self._get_element_at_path(result, path2)
                self._set_element_at_path(result, path1, val2)
                self._set_element_at_path(result, path2, val1)

        return result

    def _format_join_order_to_string(self, join_order: List) -> str:
        """Format a list of aliases to a string."""
        if not isinstance(join_order, list):
            return str(join_order)

        elements = []
        for item in join_order:
            elements.append(self._format_join_order_to_string(item))

        return f"[{', '.join(elements)}]"

    def _get_index_of_join_node(self, join_node_id: str) -> int:
        """
        Get the index of a join node in the join order list.

        Args:
            join_node_id: ID of the join node
        """
        for i, (join_node, node_id) in enumerate(self.join_order):
            if node_id == join_node_id:
                return i

    def _get_root(self):
        for node, node_data in self.graph.nodes(True):
            if node_data['is_root']:
                return node

    def _swap_join_order(self, modification: Union[JoinOrderModification, JoinOrderModificationSpecced]):
        if isinstance(modification, JoinOrderModification): # get node by id
            join_node_1_id: str = modification.join_order_1_id
            join_node_2_id: str = modification.join_order_2_id
        else: # is JoinOrderModificationSpecced
            print("isJoinOrderModificationSpecced")
            print("modification.join_order_1:", modification.join_order_1)
            join_node_1_id: str = self._get_join_node_by_type_and_alias(modification.join_type_1, modification.join_order_1)
            join_node_2_id: str = self._get_join_node_by_type_and_alias(modification.join_type_2, modification.join_order_2)

        # Copy node data
        join_node_1_data = deepcopy(self.graph.nodes(True)[join_node_1_id])
        join_node_2_data = deepcopy(self.graph.nodes(True)[join_node_2_id])

        # Save parents
        join_node_1_parent = None
        join_node_2_parent = None
        if not join_node_1_data['is_root']:
            join_node_1_parent = deepcopy(list(self.graph.predecessors(join_node_1_id))[0])
        if not join_node_2_data['is_root']:
            join_node_2_parent = deepcopy(list(self.graph.predecessors(join_node_2_id))[0])

        # Save children
        join_node_1_children = deepcopy(list(self.graph.successors(join_node_1_id)))
        join_node_2_children = deepcopy(list(self.graph.successors(join_node_2_id)))

        # Remove nodes
        self.graph.remove_node(join_node_1_id)
        self.graph.remove_node(join_node_2_id)

        print("join_node_1_data:", join_node_1_data)
        print("join_node_2_data:", join_node_2_data)

        # Add nodes back with swapped order
        self.graph.add_node(join_node_1_id, **join_node_2_data)
        self.graph.add_node(join_node_2_id, **join_node_1_data)

        # Re-add parents
        if join_node_1_parent is not None:
            self.graph.add_edge(join_node_1_parent, join_node_1_id)

        if join_node_2_parent is not None:
            self.graph.add_edge(join_node_2_parent, join_node_2_id)

        # Re-add children
        for child in join_node_1_children:
            self.graph.add_edge(join_node_1_id, child)
        for child in join_node_2_children:
            self.graph.add_edge(join_node_2_id, child)

        join_node_1_order = join_node_1_data.get('_join_order')
        join_node_2_order = join_node_2_data.get('_join_order')
        join_on_1 = join_node_1_data['join_on']
        join_on_2 = join_node_2_data['join_on']

        # Then Swap the join orders
        join_node_1_order = self._swap_or_replace_elements(join_node_1_order, join_on_1[0], join_on_2[0])
        join_node_1_order = self._swap_or_replace_elements(join_node_1_order, join_on_1[1], join_on_2[1])

        print("post change join_node_1_order:", join_node_1_order)

        # print("pre change join_node_2_order:", join_node_2_order)
        join_node_2_order = self._swap_or_replace_elements(join_node_2_order, join_on_2[0], join_on_1[0])
        join_node_2_order = self._swap_or_replace_elements(join_node_2_order, join_on_2[1], join_on_1[1])

        # print("post change join_node_2_order:", join_node_2_order)

        join_order_str_1 = self._format_join_order_to_string(join_node_1_order)
        join_order_str_2 = self._format_join_order_to_string(join_node_2_order)

        isRoot1 = join_node_1_data.get('is_root')
        isRoot2 = join_node_2_data.get('is_root')

        join_order_update_d = {
            join_node_1_id: {'_join_order': join_node_1_order, 'join_order': join_order_str_1, 'is_root': isRoot1},
            join_node_2_id: {'_join_order': join_node_2_order, 'join_order': join_order_str_2, 'is_root': isRoot2}
        }

        # Update the _join_order attribute of the 2 nodes
        nx.set_node_attributes(self.graph, join_order_update_d)

        # update join order list (class)
        join_node_1_index = self._get_index_of_join_node(join_node_1_id)
        join_node_2_index = self._get_index_of_join_node(join_node_2_id)
        print("join_node_1_index:", join_node_1_index)
        print("join_node_2_index:", join_node_2_index)
        self.join_order[join_node_1_index], self.join_order[join_node_2_index] = (join_node_1_order, join_node_1_id), (join_node_2_order, join_node_2_id)

        other_join_order_update = {}

        # Update _join_order attribute of all other joins (except for the 2 nodes), starting from the root
        for _, node_id in self.join_order:
            if node_id != join_node_1_id and node_id != join_node_2_id:
                _join_order = self.graph.nodes(True)[node_id].get('_join_order')
                print("other node _join_order to change:", _join_order)
                print("join_on_1:", join_on_1)
                print("join_on_2:", join_on_2)
                _join_order = self._swap_or_replace_elements(_join_order, join_on_1[0], join_on_2[0])
                _join_order = self._swap_or_replace_elements(_join_order, join_on_1[1], join_on_2[1])
                print("updated order:", _join_order)
                join_order_str = self._format_join_order_to_string(_join_order)
                other_join_order_update[node_id] = {'_join_order': _join_order, 'join_order': join_order_str}

                # update join order list (class)
                join_node_index = self._get_index_of_join_node(node_id)
                self.join_order[join_node_index] = (_join_order, node_id)

        nx.set_node_attributes(self.graph, other_join_order_update)

        # Then for each join in join order list, check its children's join order and see if it is in its own join order list. If not, append them to a change list
        re_parent_lst = []
        for join_order, node_id in self.join_order:
            children_to_check = list(self.graph.successors(node_id))
            for child in children_to_check:
                if child in join_order:
                    continue
                else:
                    # check if child is a subquery node and skip if it is
                    child_data = self.graph.nodes(True)[child]
                    if child_data.get('_subplan'):
                        continue
                    else:
                        # Mark the child for re-parenting
                        re_parent_lst.append(child)
                        # remove the edge between the join node and the child
                        self.graph.remove_edge(node_id, child)
        print("re_parent_lst:", re_parent_lst)
        print("join_order:", self.join_order)
        # Then for each node in the change list, iterate over each node in the join order list and see which node has the child's join order in its own. If found, add an edge between the two nodes
        for node in re_parent_lst:
            for join_order, node_id in self.join_order:
                node_data = self.graph.nodes(True)[node]
                node_join_order = node_data.get('_join_order')
                """if type(node_join_order) == set:
                    if len(node_join_order) == 1:
                        node_join_order = next(iter(node_join_order))
                    else:
                        node_join_order = list(node_join_order)"""
                print("node_join_order:", node_join_order)
                if node_join_order in join_order:
                    self.graph.add_edge(node_id, node)
                    break

        """# Tag the subquery node near another non-scan node that has the same table (join order, map from alias to get table):
        # Check the join node's join order: if similar non-scan node is the left table (outer), tag the subquery node under the join.
        # If the similar non-scan node is the inner table, tag the subquery node under the leaf node of that similar node

        # Get list of subquery nodes
        subquery_nodes = [node for node, data in self.graph.nodes(data=True) if data.get('_subplan')]

        for subquery_node in subquery_nodes:
            # Get subquery node join order
            subquery_node_data = self.graph.nodes(True)[subquery_node]
            subquery_node_join_order = subquery_node_data.get('_join_order')
            table_name = self.alias_map[subquery_node_data['aliases'][0]]

            # Get the join node's join order
            for join_order, node_id in self.join_order:
                join_node_data = self.graph.nodes(True)[node_id]
                join_node_join_order = join_node_data.get('_join_order')
                if join_node_join_order == subquery_node_join_order:"""





    def apply_modifications(self, match_node_by_id: bool = True) -> nx.DiGraph:
        """
        Apply all stored modifications to the query plan graph.

        Returns:
            Modified NetworkX DiGraph
        """
        if not self.modifications:
            pass
            # raise ValueError("No modifications have been added")
        else:
            if match_node_by_id:
                for modification in self.modifications:
                    if isinstance(modification, TypeModification):
                        self._update_node_type(modification.node_id, modification.new_type)
                    else: # is JoinOrderModification
                        print("applying join order modification id")
                        self._swap_join_order(modification)
            else:
                for modification in self.modifications:
                    if isinstance(modification, TypeModification):
                        matching_nodes = self._find_matching_nodes(modification)
                        for node_id in matching_nodes:
                            self._update_node_type(node_id, modification.new_type)
                    else: # is JoinOrderModificationSpecced
                        print("applying join order modification specced")
                        self._swap_join_order(modification)
        self.clear_costs()
        return self.graph

    def get_total_cost(self) -> float:
        """
        Calculate the total cost by summing the 'cost' attribute of all nodes in the graph.

        Parameters:
        G (networkx.Graph): A NetworkX graph where nodes have a 'cost' attribute

        Returns:
        float: The total cost sum across all nodes

        Raises:
        KeyError: If any node is missing the 'cost' attribute
        """
        total_cost = 0

        # Iterate through all nodes and sum their costs
        for node in self.graph.nodes():
            try:
                node_cost = self.graph.nodes[node]['cost']
                total_cost += node_cost
            except KeyError:
                raise KeyError(f"Node {node} is missing the 'cost' attribute")

        return total_cost

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
            select 
            * 
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
    original_graph, jo, alias_map = parser.parse(qep_data)

    # 3. Create modifications
    # Change the sequential scan on customer table to an index scan
    scan_modification = TypeModification(
        node_type=NodeType.SCAN,
        original_type=ScanType.SEQ_SCAN.value,
        new_type=ScanType.BITMAP_HEAP_SCAN.value,
        tables={'c'},
        node_id="SOMESTRING"
    )

    # Change the nested loop join to a hash join
    join_modification = TypeModification(
        node_type=NodeType.JOIN,
        original_type=JoinType.HASH_JOIN.value,
        new_type=JoinType.NESTED_LOOP.value,
        tables={'c', 'o', "l", "s"},
        node_id="SOMESTRING"
    )

    # Change the join order of two joins
    join_order_modification = JoinOrderModificationSpecced(
        join_order_1=('o', 'c'),
        join_type_1=JoinType.NESTED_LOOP.value,
        join_order_2=('l', 's'),
        join_type_2=JoinType.HASH_JOIN.value
    )

    # 4. Apply modifications
    modifier = QEPModifier(original_graph, jo, alias_map)
    modifier.add_modification(scan_modification)
    modifier.add_modification(join_modification)
    modifier.add_modification(join_order_modification)

    modified_graph = modifier.apply_modifications(False)

    # 5. Visualize the modified graph
    visualizer = QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_qep_tree.png")
