from typing import List, Optional, Union, Dict

import networkx as nx

from src.custom_types.qep_types import NodeType, TypeModification, InterJoinOrderModificationSpecced, \
    InterJoinOrderModification, IntraJoinOrderModificationSpecced, IntraJoinOrderModification, JoinType


class QEPChangeChecker:
    def __init__(self):
        self.graph: Optional[nx.DiGraph, None] = None
        self.preview_graph = None

    def _get_node_id(self, modification: Union[TypeModification, InterJoinOrderModificationSpecced, IntraJoinOrderModificationSpecced]):
        if isinstance(modification, TypeModification):
            matching_nodes = []

            for node_id, data in self.graph.nodes(data=True):
                node_type = data.get('node_type', '')

                # Check if node matches modification criteria
                if modification.node_type == NodeType.SCAN:
                    # For scan nodes, check if it's a scan on the specified table
                    node_table_aliases = set(data.get('aliases', []))
                    print("node_table_aliases:", node_table_aliases, "modification.tables:", modification.tables, "node_type:", node_type, "modification.original_type:", modification.new_type)
                    if (node_type == modification.new_type and
                            len(node_table_aliases.intersection(modification.tables)) == len(modification.tables)):
                        matching_nodes.append(node_id)

                elif modification.node_type == NodeType.JOIN:
                    # print("mod node type:", modification.node_type)
                    # For join nodes, check if it involves the specified tables
                    node_table_aliases = set(data.get('aliases', []))
                    print("node_table_aliases:", node_table_aliases, "modification.tables:", modification.tables)
                    if (node_type == modification.new_type and
                            len(node_table_aliases.intersection(modification.tables)) == len(modification.tables)):
                        matching_nodes.append(node_id)
            print("modification.node_type:", modification.node_type, NodeType.SCAN, )
            return matching_nodes[0]

        elif isinstance(modification, InterJoinOrderModificationSpecced):
            join_node_1 = None
            join_node_2 = None
            for node_id, node_data in self.graph.nodes(data=True):
                if "join_on" in node_data:
                    print("node_data['join_on']:", node_data['join_on'], "modification.join_order_2:",
                          modification.join_order_2, node_data['node_type'], modification.join_type_2)
                if node_data['node_type'] in JoinType and node_data['node_type'] != "Hash" and "join_on" in node_data:
                    if node_data['join_on'] == modification.join_order_1 and node_data['node_type'] == modification.join_type_1:
                        join_node_1 = node_id

                    elif node_data['join_on'] == modification.join_order_2 and node_data['node_type'] == modification.join_type_2:
                        join_node_2 = node_id

            print("join_node_1:", join_node_1, "join_node_2:", join_node_2)

            return join_node_1, join_node_2

        elif isinstance(modification, IntraJoinOrderModificationSpecced):
            join_node = None
            for node_id, node_data in self.graph.nodes(data=True):
                if node_data['_join_order'] == modification.join_order and node_data['join_type'] == modification.join_type:
                    join_node = node_id

            return join_node

    def _check_type_change(self, modification: TypeModification, node_id: str) -> bool:
        node_data = self.graph.nodes(data=True)[node_id]
        if node_data['node_type'] == modification.new_type:
            return True
        else:
            return False

    def _check_inter_join_order_change(
            self,
            modification: Union[InterJoinOrderModificationSpecced, InterJoinOrderModification],
            join_node_1_id: str,
            join_node_2_id: str
    ) -> bool:
        print("_check_inter_join_order_change")
        node_1 = self.graph.nodes(data=True)[join_node_1_id]
        node_2 = self.graph.nodes(data=True)[join_node_2_id]

        preview_node_1 = self.preview_graph.nodes(data=True)[join_node_1_id]
        preview_node_2 = self.preview_graph.nodes(data=True)[join_node_2_id]

        print("preview_node_1:", preview_node_1, "preview_node_2:", preview_node_2)
        print("node_1:", node_1, "node_2:", node_2)

        if node_1['_join_order'] == preview_node_1['_join_order'] and node_1['node_type'] == preview_node_1['node_type']:
            if node_2['_join_order'] == preview_node_2['_join_order']:
                return True
        return False

    def _check_intra_join_order_change(
            self,
            modification: Union[IntraJoinOrderModificationSpecced, IntraJoinOrderModification],
            join_node_id: str
    ) -> bool:
        node = self.graph.nodes(data=True)[join_node_id]
        preview_node = self.preview_graph.nodes(data=True)[join_node_id]

        if node['_join_order'] == preview_node['_join_order'] and node['node_type'] == preview_node['node_type']:
            return True
        else:
            return False

    def check(self, graph: nx.DiGraph, preview_graph: nx.DiGraph, modification_lst: List, identify_by_node_id: bool = True) -> List:
        self.graph = graph
        self.preview_graph = preview_graph
        changes_lst = []

        if identify_by_node_id:  # use node_id to identify nodes
            for modification in modification_lst:  # use specced modifications
                if isinstance(modification, TypeModification):
                    change = self._check_type_change(modification, modification.node_id)
                    changes_lst.append((modification, change))

                elif isinstance(modification, InterJoinOrderModification):
                    change = self._check_inter_join_order_change(modification, modification.join_node_1_id, modification.join_node_2_id)
                    changes_lst.append((modification, change))

                elif isinstance(modification, IntraJoinOrderModification):
                    change = self._check_intra_join_order_change(modification, modification.join_node_id)
                    changes_lst.append((modification, change))

                else:
                    raise ValueError("Invalid modification type")
        else:
            for modification in modification_lst:  # use specced modifications
                if isinstance(modification, TypeModification):
                    node_id = self._get_node_id(modification)
                    change = self._check_type_change(modification, node_id)
                    changes_lst.append((modification, change))

                elif isinstance(modification, InterJoinOrderModificationSpecced):
                    join_node_1_id, join_node_2_id = self._get_node_id(modification)
                    #print("join_node_1_id, join_node_2_id:", join_node_1_id, join_node_2_id)
                    if join_node_1_id is None or join_node_2_id is None:
                        change = False
                    else:
                        change = self._check_inter_join_order_change(modification, join_node_1_id, join_node_2_id)
                    changes_lst.append((modification, change))

                elif isinstance(modification, IntraJoinOrderModificationSpecced):
                    join_node_id = self._get_node_id(modification)
                    change = self._check_intra_join_order_change(modification, join_node_id)
                    changes_lst.append((modification, change))

                else:
                    raise ValueError("Invalid modification type")
        print(changes_lst)
        return changes_lst
