import uuid
from typing import Dict, List, Set, Tuple, Any, Hashable

import networkx as nx
from networkx import DiGraph
from networkx.algorithms.dag import descendants

from src.custom_types.qep_types import NodeType, ScanType, JoinType
import re

class QEPParser:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.root_node_id = None
        self.alias_map = {}  # alias: table_name
        self.condition_keys = ['Filter', 'Join Filter', 'Hash Cond', 'Recheck Cond', 'Index Cond', 'Merge Cond',
                               'Cache Key']
        self.lowest_level = 0

    def map_subquery_aliases_to_alternative(self, subquery_alias) -> str:
        """Map subquery alias to alternative."""
        table_name = self.alias_map[subquery_alias]
        print("table_name:", table_name)
        for alias, name in self.alias_map.items():
            if name == table_name and alias != subquery_alias:
                return alias

    def _get_single_join_pair(self, node_id: str) -> Tuple[str, str]:
        node_data = self.graph.nodes(data=True)[node_id]
        condition_found = False
        if node_data['node_type'] == "Nested Loop":
            children = self.graph.successors(node_id)
            # if nested loop, get join pair from condition of child node that is not a join
            for child in children:
                child_node_data = self.graph.nodes(data=True)[child]
                if "Join" not in child_node_data['node_type'] and child_node_data['node_type'] != "Nested Loop":
                    print("child type:", child_node_data['node_type'])
                    for attribute in self.condition_keys:
                        if attribute in child_node_data and attribute != "Join Filter" and attribute != 'Cache Key':
                            condition_aliases = self._extract_aliases_from_condition(child_node_data[attribute])
                            print("attribute:", attribute)
                            print("nested loop join condition:", child_node_data[attribute])
                            print("condition_aliases:", condition_aliases)
                            if len(condition_aliases) > 1:
                                condition_found = True
                                return tuple(self._extract_aliases_from_condition(child_node_data[attribute]))

            if not condition_found:
                # if condition still not found, check its non join descendants:
                print("current node type:", self.graph.nodes(True)[node_id]['node_type'])
                print("current join order:", self.graph.nodes(True)[node_id]['join_order'])
                for child in self.graph.successors(node_id):
                    # make sure child is non join before proceeding
                    if not ("Join" in self.graph.nodes(data=True)[child]['node_type'] or self.graph.nodes(data=True)[child]['node_type'] == "Nested Loop"):
                        print("child type:", self.graph.nodes(data=True)[child]['node_type'])
                        descendants = nx.descendants(self.graph, child)
                        for descendant in descendants: # check its descendants
                            print("descendant type:", self.graph.nodes(data=True)[descendant]['node_type'])
                            descendant_node_data = self.graph.nodes(data=True)[descendant]
                            for attribute in self.condition_keys: # get condition from descendants
                                if attribute in descendant_node_data and attribute != "Join Filter" and attribute != 'Cache Key':
                                    condition_aliases = set(self._extract_aliases_from_condition(descendant_node_data[attribute]))
                                    print("self.alias_map:", self.alias_map)
                                    descendant_alias = descendant_node_data['aliases']
                                    if len(descendant_alias) == 1:
                                        descendant_alias = next(iter(descendant_alias))
                                        print("descendant_node_data:", descendant_node_data)
                                        if descendant_node_data["_subplan"]:
                                            descendant_alias = set(self.map_subquery_aliases_to_alternative(descendant_alias))
                                        print('descendant_alias:', descendant_alias)
                                    condition_aliases = condition_aliases.union(descendant_alias) # add aliases of descendant node
                                    if len(condition_aliases) > 1: # if condition has more than one alias, return it
                                        print("non join descendant join condition:", descendant_node_data[attribute])
                                        print("aliases:", condition_aliases)
                                    else:
                                        continue
                                    return tuple(condition_aliases)

        # if not nested loop, can get join tables (alias) from join condition ( ___ Cond)
        else:
            for attribute in self.condition_keys:
                if attribute != "Join Filter" and attribute in node_data:
                    print("non nested loop join condition:", node_data[attribute])
                    print("aliases:", self._extract_aliases_from_condition(node_data[attribute]))
                    return tuple(self._extract_aliases_from_condition(node_data[attribute]))

        print("still not found:", node_data['node_type'])

    def _get_join_pairings_in_order(self) -> Tuple[List[Tuple[Tuple[str, str], str]], Dict]:
        # incrementally parse each join node from bottom up (and left to right, each level will be a list) to get join pairings
        # Start from the lowest level, travel upwards breadth-first
        # print("lowest level:", self.lowest_level)
        ordered_join_pairs = []
        ordered_join_pairings_d = {}  # {node_id: {'join_on': (alias, alias)}}
        for node_level in range(self.lowest_level, -1, -1):
            # print("processing for node_level:", node_level)
            nodes = self._get_nodes_by_level(node_level)
            for node_id in nodes:
                node_data = self.graph.nodes(data=True)[node_id]
                if "Join" in node_data['node_type'] or node_data['node_type'] == "Nested Loop":
                    join_pair = self._get_single_join_pair(node_id)
                    if join_pair:
                        print("_join_table_aliases:", node_data['_join_table_aliases'])
                        print("nested loop join pair:", join_pair)
                        _join_order = node_data['_join_order']
                        right = join_pair[-1]
                        print("_join_table_aliases:", _join_order)
                        if right != _join_order[-1]: # right of pair is not actually right table in order
                            join_pair = (join_pair[1], join_pair[0]) # thus switch it
                            print("switched join pair:", join_pair)
                    else:
                        if 'Join Filter' in node_data.keys():
                            join_pair = tuple(self._extract_aliases_from_condition(node_data['Join Filter']))
                            print("join pair from Join Filter:", join_pair)
                        else:
                            _join_order = node_data['_join_order']
                            if len(_join_order) == 2:
                                join_pair = tuple(_join_order)
                                print("2 length join pair:", join_pair)

                    ordered_join_pairings_d[node_id] = {'join_on': join_pair}

                    ordered_join_pairs.append((join_pair, node_id))
        return ordered_join_pairs, ordered_join_pairings_d

    @staticmethod
    def _get_join_order_aliases(join_order_str: str):
        join_order_str = join_order_str.replace("[", "").replace("]", "")
        return join_order_str.split(", ")

    def _format_join_order_to_string(self, join_order: List) -> str:
        """Format a list of aliases to a string."""
        if not isinstance(join_order, list):
            return str(join_order)

        elements = []
        for item in join_order:
            elements.append(self._format_join_order_to_string(item))

        return f"[{', '.join(elements)}]"

    def _resolve_table_name(self, identifier: str) -> str:
        """
        Resolve a table identifier to its full original name.
        Returns the original identifier if no mapping exists.
        """
        return self.alias_map.get(identifier.lower(), identifier)

    def _register_alias(self, alias: str, table_name: str):
        """Register a table alias."""
        self.alias_map[alias.lower()] = table_name

    def _extract_aliases_from_condition(self, condition: str) -> Set[str]:
        """Extract all table aliases from a condition string."""
        # Extract all words from the condition
        condition = condition.replace("(", "")
        condition = condition.replace(")", "")
        words = condition.split()
        aliases = set()

        # Check if each word is an alias
        for word in words:
            print("word:", word)
            candidate = word.split('.')[0]  # only consider the left side of the dot
            # Check if the word is a valid alias
            if candidate.lower() in self.alias_map:
                aliases.add(candidate.lower())

        return aliases

    def _parse_node(self, node_data: Dict, node_level: int, parent_node_id: str = None) -> str:
        """Parse a single node in the QEP data."""
        # Setup node data first
        """Parse a single node and its children."""

        node_id = str(uuid.uuid4())
        tables = set()
        aliases = set()
        try:
            node_type = node_data['Node Type']
        except KeyError:
            print(node_data)
            raise ValueError("Node Type not found in node data: \n{}".format(node_data))

        # Check if node is part of subquery
        if 'Subplan Name' in node_data:
            subplan_status = True
        else:
            subplan_status = False

        # Keep track of lowest level for bottom-up traversal later
        if node_level > self.lowest_level:
            self.lowest_level = node_level

        # Register aliases if it's a scan node
        if node_type in ScanType:
            if 'Alias' in node_data:
                # wrapped in if block to handle the edge case of BitMap Index Scan not having an alias attribute
                alias = node_data['Alias']
                self._register_alias(alias, node_data['Relation Name'])
                aliases.add(alias)

        # Node is root if it does not have a parent
        if parent_node_id is None:
            is_root = True
            self.root_node_id = node_id
        else:
            is_root = False

        node_attrs = {
            'node_type': node_type,
            'tables': tables,
            'cost': node_data.get('Total Cost', -1.0),
            'is_root': is_root,
            'aliases': aliases,
            '_node_level': node_level,
            '_subplan': subplan_status,
        }

        # Get Conditions
        for key in self.condition_keys:
            if key in node_data:
                if "Cond" in key:
                    key.replace("Cond", "On")
                node_attrs[key] = node_data[key]

                # Only extract aliases if it's not a scan node
                if node_type not in ScanType:
                    node_attrs['aliases'].update(self._extract_aliases_from_condition(node_data[key]))

        # Add node to graph
        self.graph.add_node(node_id, **node_attrs)

        # Connect to parent if not root
        if parent_node_id is not None:
            self.graph.add_edge(parent_node_id, node_id)

        # Recursively parse children
        if 'Plans' in node_data:
            for child_node_data in node_data['Plans']:
                self._parse_node(child_node_data, node_level + 1, node_id)

        return node_id

    @staticmethod
    def _extract_plan(plan: List) -> Dict:
        """Extract the plan data from the nested list(s)."""
        while True:
            if not plan:
                raise RuntimeError("No plan found")

            # Incrementally traverse deeper into the nested List structure with each iteration of the while loop
            plan = plan[0]

            # Return object if it's a dictionary (that means we have found the plan)
            if type(plan) == dict and 'Plan' in plan.keys():
                return plan['Plan']

    def _get_nodes_by_level(self, node_level: int) -> List:
        return [node_id for (node_id, node_data) in self.graph.nodes(data=True) if
                node_data['_node_level'] == node_level]

    def _get_join_order(self) -> Dict:
        join_order = {}  # {node_id: {'join_order': [alias, alias, alias]}, node_id: {'join_order': [alias, alias, alias]}}
        # Start from the lowest level, travel upwards breadth-first
        # print("lowest level:", self.lowest_level)
        for node_level in range(self.lowest_level, -1, -1):
            # print("processing for node_level:", node_level)
            nodes = self._get_nodes_by_level(node_level)
            for node_id in nodes:
                node_data = self.graph.nodes(data=True)[node_id]
                if not ("Join" in node_data['node_type'] or node_data['node_type'] == "Nested Loop"):
                    print(f"processing {node_data['node_type']} on {node_data['aliases']}")
                    # If it's not a join node, copy the join order from the child OR initialize from aliases attribute
                    children = list(self.graph.successors(node_id))
                    if len(children) > 1:
                        raise ValueError("Non-join node has more than one child:\n {}".format(node_data))
                    else:
                        if len(children) > 0:  # is not leaf, so copy from child, unless child's alias is empty
                            for child in children:
                                child_join_order = join_order[child]['_join_order']
                                print("child_join_order:", child_join_order)
                                if len(child_join_order) > 0:  # if child has join order, copy it
                                    print(
                                        f"Processing node type {node_data['node_type']} on {node_data['aliases']} from non leaf, child has join order")
                                    # if child has only one alias, unpack it
                                    if len(child_join_order) == 1:
                                        child_join_order = next(iter(child_join_order))
                                    join_order[node_id] = {'_join_order': child_join_order}
                                else:  # if child has no join order, initialize from aliases (to handle edge case of BitMap Index Scan not having alias attribute)x
                                    aliases = node_data['aliases']
                                    # if node has only one alias, unpack it
                                    if len(aliases) == 1:
                                        aliases = next(iter(aliases))
                                    join_order[node_id] = {'_join_order': aliases}
                                    print(
                                        f"Processing node type {node_data['node_type']} on {node_data['aliases']} from non leaf, child doesn't have join order")
                        else:  # is leaf, so initialize from aliases
                            print(
                                f"Processing node type {node_data['node_type']} on {node_data['aliases']} from leaf")
                            aliases = node_data['aliases']
                            # if node has only one alias, unpack it
                            if len(aliases) == 1:
                                aliases = next(iter(aliases))
                            join_order[node_id] = {'_join_order': aliases}

                else:  # is a join node, thus we need to merge the join orders of the children
                    print(
                        f"Processing node type {node_data['node_type']} on {node_data['aliases']}")
                    children = self.graph.successors(node_id)
                    current_node_order = []
                    for child in children:
                        # check if child is a subplan node, if yes ignore that as pg_hint_plan does not support subplan table aliasing
                        if self.graph.nodes(data=True)[child]['_subplan']:
                            continue
                        child_join_order = join_order[child]['_join_order']
                        # if child has only one alias, unpack it
                        if len(child_join_order) == 1:
                            child_join_order = next(iter(child_join_order))
                        current_node_order.append(child_join_order)
                    join_order[node_id] = {'_join_order': current_node_order}
                print(
                    f"Join order for node type {node_data['node_type']} on {node_data['aliases']} is {join_order[node_id]['_join_order']}")
        return join_order

    def get_node_positions(self) -> Dict[str, Dict[str, str]]:
        node_positions_d = {}  # {node_id: {position: 'l'/'r'/'c'}}

        for node_id, node_data in self.graph.nodes(True):
            # only care for the positions of non subquery nodes
            if not node_data.get('_subplan'):
                # check not root
                if not node_data.get('is_root'):
                    # check parent if node is only child
                    parent = list(self.graph.predecessors(node_id))[0]
                    parent_node_data = self.graph.nodes(True)[parent]
                    if len(list(self.graph.successors(parent))) == 1: # only child
                        # therefore put 'c' for center
                        node_positions_d[node_id] = {'position': 'c'}
                    else: # not only child
                        # check if node is left or right child by getting join order
                        parent_join_order = parent_node_data.get('_join_order')
                        right_order = parent_join_order[-1]
                        node_join_order = node_data.get('_join_order')
                        print("left_join_order:", parent_join_order, "node_type:", node_data.get('node_type'), "node_join_order:", node_join_order)
                        if right_order == node_join_order:
                            node_positions_d[node_id] = {'position': 'r'}
                        else:
                            node_positions_d[node_id] = {'position': 'l'}
                else:
                    # root node
                    node_positions_d[node_id] = {'position': 'c'}
            else:
                # subquery node set as 's' which means ignore positioning
                node_positions_d[node_id] = {'position': 's'}

        return node_positions_d

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

    @staticmethod
    def _flatten_list(nested_list: List) -> List:
        flat_list = []

        def flatten(lst):
            for item in lst:
                if isinstance(item, (list, tuple)):
                    flatten(item)
                else:
                    flat_list.append(item)

        flatten(nested_list)
        return flat_list

    def _get_join_node_aliases(self, join_nodes: List[Tuple[Tuple, str]]) -> Dict:
        join_aliases_d = {} # {node_id: {'join_aliases': [alias, alias]}}
        for join_pair, join_node_id in join_nodes:
            node_data = self.graph.nodes(data=True)[join_node_id]
            join_aliases = node_data['_join_table_aliases']
            join_aliases_d[join_node_id] = {'aliases': join_aliases}

        #print("join_aliases_d:", join_aliases_d)
        return join_aliases_d

    def _replace_node_id_from_join_on(self, join_node_id_map: Dict):
        node_replace = {}
        for node_id, node_data in self.graph.nodes(data=True):
            if 'join_on' in node_data:
                node_join_on = node_data.get('join_on')
                og_node_id = join_node_id_map[node_join_on]
                node_replace[node_id] = og_node_id

        return node_replace

    def _replace_node_id_from_alias(self, alias_node_id_map: Dict):
        node_replace = {}
        for node_id, node_data in self.graph.nodes(data=True):
            if 'aliases' in node_data and node_data['node_type'] in ScanType and node_data['node_type'] != "Hash":
                if "_subplan" not in node_data or not node_data['_subplan']:
                    node_alias = node_data.get('aliases')
                    if len(node_alias) == 1:
                        node_alias = next(iter(node_alias))
                        og_node_id = alias_node_id_map[node_alias]
                        node_replace[node_id] = og_node_id
        print("node_replace_alias:", node_replace)
        return node_replace

    def _get_swappability(self) -> Dict[str, Dict[str, bool]]:
        swappablity_d = {}
        for node_id, node_data in self.graph.nodes(True):
            # Check if it is a subquery node:
            if node_data['_subplan']:
                print("Subquery node found:", node_data['node_type'])
                swappablity_d[node_id] = {'_swappable': False}
            else:
                # Check if its join node:
                if "Join" in node_data['node_type'] or node_data['node_type'] == "Nested Loop":
                    swappablity_d[node_id] = {'_swappable': True}
                else: # if not join node
                    # Check if parent is join
                    parent = list(self.graph.predecessors(node_id))[0]
                    parent_node_data = self.graph.nodes(True)[parent]
                    if "Join" in parent_node_data['node_type'] or parent_node_data['node_type'] == "Nested Loop":
                        swappablity_d[node_id] = {'_swappable': True}
                    else:
                        swappablity_d[node_id] = {'_swappable': False}
        return swappablity_d


    def parse(self, qep_data: List, join_node_id_map: Dict, scan_node_id_map: Dict) -> Tuple[nx.DiGraph, Dict, Dict, Dict, Dict]:
        """Parse the QEP data into a networkX graph."""
        self.graph.clear()

        plan = self._extract_plan(qep_data)

        # Parse the root node, the parse_node function will recursively be called
        self._parse_node(plan, node_level=0, parent_node_id=None)

        # Inherit Subplan trait
        for node_id, data in self.graph.nodes(data=True):
            if data['_subplan']:
                for child in descendants(self.graph, node_id):
                    nx.set_node_attributes(self.graph, {child: {'_subplan': True}})

        # Resolve table names for aliases used:
        for node_id, data in self.graph.nodes(data=True):
            if data['node_type'] in ScanType:
                print(data)
                table_names = [self._resolve_table_name(alias) for alias in data['aliases']]
                nx.set_node_attributes(self.graph, {node_id: {'tables': set(table_names)}})

        # Get Join Order
        join_order_dict = self._get_join_order()

        # Set join order as node attribute
        nx.set_node_attributes(self.graph, join_order_dict)

        # Get Join Order String
        join_order_str_dict = {}
        for node_id in join_order_dict:
            join_order = join_order_dict[node_id]['_join_order']
            if type(join_order) == list and len(join_order) > 1:
                print("debug join order str:", join_order_dict[node_id]['_join_order'])
                join_order_str_dict[node_id] = {'join_order': self._format_join_order_to_string(join_order)}

        # Set join order string as graph attribute
        nx.set_node_attributes(self.graph, join_order_str_dict)

        # Get join table aliases
        join_table_aliases = {}
        for node_id in join_order_str_dict:
            join_order_str = join_order_str_dict[node_id]['join_order']
            join_table_aliases[node_id] = {'_join_table_aliases': self._get_join_order_aliases(join_order_str)}

        # Set join table aliases as node attribute
        nx.set_node_attributes(self.graph, join_table_aliases)

        # Ordered Join
        ordered_join_pairs, join_relation_aliases = self._get_join_pairings_in_order()

        # Set join relations as node attribute
        nx.set_node_attributes(self.graph, join_relation_aliases)

        print("ordered_join_pairs:", ordered_join_pairs)

        # Get node positions
        node_positions = self.get_node_positions()

        # Set node positions as node attribute
        nx.set_node_attributes(self.graph, node_positions)

        # Get join node aliases
        join_node_aliases = self._get_join_node_aliases(ordered_join_pairs)

        # Set join node aliases
        nx.set_node_attributes(self.graph, join_node_aliases)

        print("join_node_id_map:", join_node_id_map)

        if join_node_id_map:
            # Replace node id from join on
            join_node_replace = self._replace_node_id_from_join_on(
                join_node_id_map
            )
            self.graph = nx.relabel_nodes(self.graph, join_node_replace)

            # Replace node ids in ordered join pairs
            ordered_join_pairs = [(join_pair, join_node_replace[node_id]) for join_pair, node_id in ordered_join_pairs]
        else:
            join_node_id_map = {}

            # Return the node ids for the ordered join pairs
            for join_pair, node_id in ordered_join_pairs:
                join_node_id_map[join_pair] = node_id
                join_node_id_map[(join_pair[-1], join_pair[0])] = node_id


        if scan_node_id_map:
            # Replace node id from alias
            print("scan node id map exists")
            alias_node_replace = self._replace_node_id_from_alias(
                scan_node_id_map
            )
            print("alias_node_replace:", alias_node_replace)
            self.graph = nx.relabel_nodes(self.graph, alias_node_replace)

        else:
            scan_node_id_map = {}

            # Return the node ids for scans
            for node_id, node_data in self.graph.nodes(data=True):
                if node_data['node_type'] in ScanType and node_data['node_type'] != "Hash":
                    for alias in node_data['aliases']:
                        scan_node_id_map[alias] = node_id

        swap_d = self._get_swappability()

        # set swappability as node attribute
        nx.set_node_attributes(self.graph, swap_d)

        return self.graph, ordered_join_pairs, self.alias_map, join_node_id_map, scan_node_id_map


if __name__ == "__main__":
    from src.database.qep.qep_visualizer import QEPVisualizer
    from src.settings.filepaths import VIZ_DIR
    from src.database.databaseManager import DatabaseManager

    # 1. Set up the database and get the original query plan
    db_manager = DatabaseManager('TPC-H')
    query = """
        select 
        /*+ Leading( ( ( (l2 l s) o) c) ) NestLoop(c o l s) */
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
    original_graph, ordered_join_pairs, alias_map, join_id  = parser.parse(qep_data)

    # 3. Visualize the original plan
    QEPVisualizer(original_graph).visualize(VIZ_DIR / "original_qep.png")

