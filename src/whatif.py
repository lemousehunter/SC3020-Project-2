from typing import Optional, List, Set, Dict, Union, Tuple

import networkx as nx

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_change_checker import QEPChangeChecker
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_modifier import QEPModifier
from src.database.query_modifier import QueryModifier
from src.custom_types.qep_types import TypeModification, InterJoinOrderModification, IntraJoinOrderModification, \
    JoinType
from src.database.hint_generator import HintConstructor


class QueryPlanManager:
    """Manages query plan operations and modifications"""

    def __init__(self):
        self.original_graph: Optional[nx.DiGraph] = None
        self.ordered_relation_pairs: Optional[List[Set[str]]] = None
        self.alias_map: Optional[Dict[str, str]] = None
        self.parser = QEPParser()
        self.preview_graph: Optional[nx.DiGraph]  = None
        self.join_node_id_map: Optional[Dict[str, str]] = None
        self.query_checker = QEPChangeChecker()
        self.scan_node_id_map = None

    def generate_plan(self, query: str, db_connection: DatabaseManager) -> Dict:
        """Generate query execution plan"""
        qep_data = db_connection.get_qep(query)
        self.original_graph, self.ordered_relation_pairs, self.alias_map, self.join_node_id_map, self.scan_node_id_map = self.parser.parse(qep_data, self.join_node_id_map, self.scan_node_id_map)

        return self._convert_graph_to_dict(self.original_graph)

    @staticmethod
    def _is_join(node_type: str):
        if node_type in JoinType and node_type != "Hash":
            return True
        else:
            return False

    def _determine_join_order_change_type(self, mod: Dict) -> Union[IntraJoinOrderModification, InterJoinOrderModification]:
        node_1_id = mod['node_1_id']
        node_2_id = mod['node_2_id']

        print(self.original_graph.nodes(True))

        node_1_data = None
        node_2_data = None

        for node_id, node_data in self.original_graph.nodes(True):
            if node_id == node_1_id:
                node_1_data = node_data
            if node_id == node_2_id:
                node_2_data = node_data

        node_1_type = node_1_data['node_type']
        node_2_type = node_2_data['node_type']

        if self._is_join(node_1_type) and self._is_join(node_2_type): # if both is Join type
            # then is InterJoinChange
            query_mod = InterJoinOrderModification(
                join_node_1_id=node_1_id,
                join_node_2_id=node_2_id
            )
            print("gotten inter join query mod:", query_mod)
        else: # if either one is not join type, then is IntraJoinChange
            # get parent of either will do
            parent = list(self.original_graph.predecessors(node_1_id))[0]
            query_mod =IntraJoinOrderModification(
                join_node_id=parent
            )
            print("gotten intra join query mod:", query_mod)

        return query_mod


    def _modify_graph(self, modifications: List[Dict]) -> Tuple[nx.DiGraph, List]:
        if not self.original_graph:
            raise ValueError("No original graph available")

        qep_modifier = QEPModifier(self.original_graph, self.ordered_relation_pairs, self.alias_map)
        modification_lst = []
        # Process modifications
        for mod in modifications:
            modification_type = mod.get('mod_type')
            if modification_type == 'TypeChange':
                query_mod = TypeModification(
                    node_type=mod.get('node_type'),
                    original_type=mod.get('original_type'),
                    new_type=mod.get('new_type'),
                    tables=set(mod.get('tables', [])),
                    node_id=mod.get('node_id', '')
                )
                qep_modifier.add_modification(query_mod)
                modification_lst.append(query_mod)
            elif modification_type == "JoinOrderChange":
                query_mod = self._determine_join_order_change_type(mod)
                modification_lst.append(query_mod)
                qep_modifier.add_modification(query_mod)
                print("Join Order Change Modification:", query_mod)
            else:
                raise ValueError(f"Invalid modification type: {modification_type}")

        print("modifications:", modification_lst)

        modified_graph, mods_lst = qep_modifier.apply_modifications()

        return modified_graph, modification_lst


    def modify_plan(self, query: str, modifications: List[Dict], db_connection: DatabaseManager) -> Dict:
        """Apply modifications to query plan"""

        original_cost = self.parser.get_total_cost()

        print("IN MODIFY PLAN")
        print("modifications:", modifications)

        modified_graph, mods_lst = self._modify_graph(modifications)

        # Generate hints
        hints, hint_list, hint_expl = HintConstructor(modified_graph, self.alias_map).generate_hints()
        modified_query = QueryModifier(query=query, hint=hints).modify()
        print("self.scan_node_id_map:", self.scan_node_id_map)

        # Get updated plan
        updated_qep = db_connection.get_qep(modified_query)
        updated_graph, updated_ordered_relation_pairs, updated_alias_map, updated_join_node_id_map, updated_scan_node_id_map = self.parser.parse(updated_qep, self.join_node_id_map, self.scan_node_id_map)

        modified_cost = self.parser.get_total_cost()

        changes_lst = self.query_checker.check(updated_graph, modified_graph, mods_lst)

        return {
            "modified_query": modified_query,
            "costs": {
                "original": original_cost,
                "modified": modified_cost
            },
            "graph": self._convert_graph_to_dict(updated_graph),
            "hints": hint_expl,
            "changes_lst": changes_lst
        }

    def preview_swap(self, mod_lst: List) -> Dict:
        """Preview the swap of two join nodes"""
        modified_graph, mods_lst = self._modify_graph(mod_lst)

        modified_graph_json = self._convert_graph_to_dict(modified_graph)

        print("modified_graph_json:", modified_graph_json)

        return modified_graph_json

    @staticmethod
    def _convert_graph_to_dict(graph: nx.DiGraph) -> Dict:
        """Convert NetworkX graph to dictionary format"""
        nodes = []
        for node_id, data in graph.nodes(data=True):
            node_type = data.get('node_type', '')
            type_name = "Join" if ("Join" in node_type or "Nest" in node_type) else \
                "Scan" if "Scan" in node_type else "Unknown"

            data_dict = {
                k: v for k, v in data.items() if not k.startswith('_')
            }

            data_dict["_join_or_scan"] = type_name
            data_dict["_isLeaf"] = len(list(graph.neighbors(node_id))) == 0
            data_dict["_id"] = node_id
            data_dict["_is_subquery_node"] = data.get('_subplan', False)
            data_dict["_swappable"] = data.get('_swappable', False)

            nodes.append(data_dict)

        edges = [{"source": u, "target": v} for u, v in graph.edges()]

        return {
            "nodes": nodes,
            "edges": edges
        }
