from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, List, Optional, Set, Tuple
import networkx as nx
from dataclasses import dataclass

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_modifier import QEPModifier
from src.database.query_modifier import QueryModifier
from src.types.qep_types import TypeModification, JoinOrderModification
from src.database.hint_generator import HintConstructor


@dataclass
class DatabaseConfig:
    """Configuration for available databases"""
    name: str
    value: str


class QueryPlanManager:
    """Manages query plan operations and modifications"""

    def __init__(self):
        self.original_graph: Optional[nx.DiGraph] = None
        self.ordered_relation_pairs: Optional[List[Set[str]]] = None
        self.alias_map: Optional[Dict[str, str]] = None
        self.parser = QEPParser()
        self.preview_graph: Optional[nx.DiGraph]  = None

    def generate_plan(self, query: str, db_connection: DatabaseManager) -> Dict:
        """Generate query execution plan"""
        qep_data = db_connection.get_qep(query)
        self.original_graph, self.ordered_relation_pairs, self.alias_map = self.parser.parse(qep_data)

        return self._convert_graph_to_dict(self.original_graph)

    def get_avail_join_swaps(self) -> Dict:
        """Get available join swaps for the current query plan"""
        if not self.original_graph:
            graph = self.preview_graph
            if not graph:
                raise ValueError("No graph available")
        else:
            graph = self.original_graph

        avail_joins = {}
        for _, node_id in self.ordered_relation_pairs:
            avail_joins[node_id] = []

        # self.order_relation_pairs holds all the join pairings
        for (join_pair, node_id) in self.ordered_relation_pairs:
            _join_order = graph.nodes[node_id].get('join_order', '')

            # Check if the join can use 

            for candidate_pair, candidate_node_id in self.ordered_relation_pairs:
                # Get candidate node's parent join aliases
                candidate_node_parent = graph.predecessors(candidate_node_id)[0]
                candidate_parent_aliases = graph.nodes[candidate_node_parent].get('aliases', [])

                # Get candidate node's children join aliases
                candidate_node_children = list(graph.successors(candidate_node_id))
                candidate_node_join_children = [child for child in candidate_node_children if 'Join' in graph.nodes[child]['node_type'] or 'Nest' in graph.nodes[child]['node_type']]
                candidate_children_aliases = [graph.nodes[child]['aliases'] for child in candidate_node_join_children]
                parent_condition = False
                child_condition = False


                # TODO: Fix this, have to check new position rather than current...
                for alias in join_pair:
                    # Check if any of the aliases of the join is in the candidate node's parent.
                    # Check for child join aliases as well. If yes to both then join swap is permissible.
                    # If no to either then join swap is not allowed
                    if alias in candidate_parent_aliases:
                        parent_condition = True
                    if alias in candidate_children_aliases:
                        child_condition = True

                if parent_condition and child_condition:
                    avail_joins[node_id].append(candidate_node_id)

        return avail_joins

    def _modify_graph(self, modifications: List[Dict]):
        if not self.original_graph:
            raise ValueError("No original graph available")

        qep_modifier = QEPModifier(self.original_graph, self.ordered_relation_pairs, self.alias_map)

        # Process modifications
        for mod in modifications:
            modification_type = mod.get('ModType')
            if modification_type == 'TypeChange':
                query_mod = TypeModification(
                    node_type=mod.get('node_type'),
                    original_type=mod.get('original_type'),
                    new_type=mod.get('new_type'),
                    tables=set(mod.get('tables', [])),
                    node_id=mod.get('node_id', '')
                )
            elif modification_type == "JoinOrderChange":
                query_mod = JoinOrderModification(
                    join_node_1_id=mod.get('join_node_1_id'),
                    join_node_2_id=mod.get('join_node_2_id')
                )
            else:
                raise ValueError(f"Invalid modification type: {modification_type}")
            qep_modifier.add_modification(query_mod)

        modified_graph = qep_modifier.apply_modifications()

        return modified_graph


    def modify_plan(self, query: str, modifications: List[Dict], db_connection: DatabaseManager) -> Dict:
        """Apply modifications to query plan"""

        original_cost = self.parser.get_total_cost()

        modified_graph = self._modify_graph(modifications)

        # Generate hints
        hints, hint_list = HintConstructor(modified_graph).generate_hints()
        modified_query = QueryModifier(query=query, hint=hints).modify()

        # Get updated plan
        updated_qep = db_connection.get_qep(modified_query)
        updated_graph, updated_ordered_relation_pairs, updated_alias_map = self.parser.parse(updated_qep)

        modified_cost = self.parser.get_total_cost()

        return {
            "modified_query": modified_query,
            "costs": {
                "original": original_cost,
                "modified": modified_cost
            },
            "graph": self._convert_graph_to_dict(updated_graph),
            "hints": {hint: "Some Explanation" for hint in hint_list}
        }

    def preview_swap(self, mod_lst: List) -> Tuple[Dict, Dict]:
        """Preview the swap of two join nodes"""
        modified_graph = self._modify_graph(mod_lst)

        modified_graph_json = self._convert_graph_to_dict(modified_graph)

        avail_join_swaps = self.get_avail_join_swaps()

        return modified_graph_json, avail_join_swaps

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

            nodes.append(data_dict)

        edges = [{"source": u, "target": v} for u, v in graph.edges()]

        return {
            "nodes": nodes,
            "edges": edges
        }


class DatabaseServer:
    """Main server class handling database operations and API endpoints"""

    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)
        self.db_connection: Optional[DatabaseManager] = None
        self.query_plan_manager = QueryPlanManager()
        self._register_routes()

    def _register_routes(self):
        """Register all API routes"""
        self.app.route('/api/database/available', methods=['GET'])(self.get_available_databases)
        self.app.route('/api/database/select', methods=['POST'])(self.select_database)
        self.app.route('/api/query/plan', methods=['POST'])(self.get_query_plan)
        self.app.route('/api/query/modify', methods=['POST'])(self.modify_query)
        self.app.route('/api/query/get_avail_join_swaps', methods=['GET'])(self.get_avail_join_swaps)
        self.app.route('/api/preview_join_swaps', methods=['POST'])(self.preview_join_swaps)

    def preview_join_swaps(self):
        """Preview join swaps based on modifications"""
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

        data = request.get_json()
        modifications = data.get('modifications', [])

        try:
            modified_graph_json, updated_avail_join_swaps = self.query_plan_manager.preview_swap(modifications)
            return jsonify({
                "status": "success",
                "message": "Preview join swaps successful",
                "networkx_object": modified_graph_json,
                "avail_joins": updated_avail_join_swaps
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def get_avail_join_swaps(self):
        """Get available join swaps for the current query plan"""
        try:
            avail_joins = self.query_plan_manager.get_avail_join_swaps()
            return jsonify({
                "status": "success",
                "message": "Available join swaps retrieved successfully",
                "avail_joins": avail_joins
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @staticmethod
    def get_available_databases():
        """Get list of available databases"""
        databases = [
            DatabaseConfig("TPC-H", "TPC-H"),
            DatabaseConfig("mysql", "MySQL"),
            DatabaseConfig("oracle", "Oracle"),
            DatabaseConfig("sqlserver", "SQL Server")
        ]
        return jsonify({"databases": [{"value": db.name, "label": db.value} for db in databases]}), 200

    def select_database(self):
        """Select and connect to a database"""
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

        data = request.get_json()
        selected_db = data.get('database')

        if not selected_db or selected_db not in ["TPC-H", "mysql", "oracle", "sqlserver"]:
            return jsonify({"status": "error", "message": "Invalid database selection"}), 400

        try:
            self.db_connection = DatabaseManager(selected_db)
            # Test connection
            self.db_connection.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
            return jsonify({
                "status": "success",
                "message": f"Connected to {selected_db}",
                "selectedDatabase": selected_db
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def get_query_plan(self):
        """Generate query execution plan"""
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

        data = request.get_json()
        query = data.get('query')

        if not query or not self.db_connection:
            if not query:
                return jsonify({"status": "QueryError", "message": "Invalid request, query is empty or not found."}), 400
            else:
                return jsonify({"status": "DatabaseError", "message": "Invalid request, database connection not found."}), 400

        try:
            result = self.query_plan_manager.generate_plan(query, self.db_connection)
            return jsonify({
                "status": "success",
                "message": "Query plan generated successfully",
                "sql_query": query,
                "networkx_object": result
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def modify_query(self):
        """Modify query plan with given modifications"""
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

        data = request.get_json()
        query = data.get('query')
        modifications = data.get('modifications', [])

        if not query or not self.db_connection:
            return jsonify({"status": "error", "message": "Invalid request"}), 400

        try:
            result = self.query_plan_manager.modify_plan(query, modifications, self.db_connection)
            return jsonify({
                "status": "success",
                "message": "QEP modifications applied successfully",
                "modified_sql_query": result["modified_query"],
                "cost_comparison": result["costs"],
                "updated_networkx_object": result["graph"],
                "hints": result["hints"]
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def run(self, debug: bool = True, port: int = 5000):
        """Run the Flask server"""
        self.app.run(debug=debug, port=port)


if __name__ == '__main__':
    server = DatabaseServer()
    server.run(debug=True, port=5000)