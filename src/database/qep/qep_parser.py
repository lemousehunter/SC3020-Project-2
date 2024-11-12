import uuid
from typing import Dict, List, Set

import networkx as nx

from src.types.qep_types import NodeType, ScanType, JoinType


class QEPParser:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.root_node_id = None
        self.alias_map = {}
        self.condition_keys = ['Filter', 'Join Filter', 'Hash Cond', 'Recheck Cond', 'Index Cond', 'Merge Cond',
                               'Cache Key']
        self.lowest_level = 0

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

    def _parse_condition(self, node_type: str):
        pass

    def _extract_aliases_from_condition(self, condition: str) -> Set[str]:
        """Extract all table aliases from a condition string."""
        # Extract all words from the condition
        words = condition.split()
        aliases = set()

        # Check if each word is an alias
        for word in words:
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
        is_root = False
        if parent_node_id is None:
            is_root = True
            self.root_node_id = node_id

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
                            join_order[node_id] = {'_join_order': node_data['aliases']}

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

    def parse(self, qep_data: List) -> nx.DiGraph:
        """Parse the QEP data into a networkX graph."""
        self.graph.clear()

        plan = self._extract_plan(qep_data)

        # Parse the root node, the parse_node function will recursively be called
        self._parse_node(plan, node_level=0, parent_node_id=None)

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

        return self.graph


if __name__ == "__main__":
    from src.database.qep.qep_visualizer import QEPVisualizer
    from src.settings.filepaths import VIZ_DIR
    from src.database.databaseManager import DatabaseManager

    # 1. Set up the database and get the original query plan
    db_manager = DatabaseManager('TPC-H')
    query = """
        select 
        /*+ Leading( ( ( (l2 l s) o) c) ) */
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
    original_graph = parser.parse(qep_data)

    # 3. Visualize the original plan
    QEPVisualizer(original_graph).visualize(VIZ_DIR / "original_qep.png")

