from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, List, Optional, Set
import networkx as nx
from dataclasses import dataclass

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_modifier import QEPModifier
from src.database.query_modifier import QueryModifier
from src.types.qep_types import QueryModification
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
        self.parser: Optional[QEPParser] = None

    def generate_plan(self, query: str, db_connection: DatabaseManager) -> Dict:
        """Generate query execution plan"""
        qep_data = db_connection.get_qep(query)
        self.parser = QEPParser()
        self.original_graph = self.parser.parse(qep_data)

        return self._convert_graph_to_dict(self.original_graph)

    def modify_plan(self, query: str, modifications: List[Dict], db_connection: DatabaseManager) -> Dict:
        """Apply modifications to query plan"""
        if not self.original_graph:
            raise ValueError("No original graph available")

        qep_modifier = QEPModifier(self.original_graph)

        # Process modifications
        for mod in modifications:
            query_mod = QueryModification(
                node_type=mod.get('node_type'),
                original_type=mod.get('original_type'),
                new_type=mod.get('new_type'),
                tables=set(mod.get('tables', [])),
                node_id=mod.get('node_id', '')
            )
            qep_modifier.add_modification(query_mod)

        modified_graph = qep_modifier.apply_modifications()

        # Generate hints
        hints, hint_list = HintConstructor(modified_graph).generate_hints(query)
        modified_query = QueryModifier(query=query, hint=hints).modify()

        # Get updated plan
        updated_qep = db_connection.get_qep(modified_query)
        updated_graph = self.parser.parse(updated_qep)

        return {
            "modified_query": modified_query,
            "costs": {
                "original": self.parser.get_total_cost(),
                "modified": self.parser.get_total_cost()
            },
            "graph": self._convert_graph_to_dict(updated_graph),
            "hints": {hint: "Some Explanation" for hint in hint_list}
        }

    def _convert_graph_to_dict(self, graph: nx.DiGraph) -> Dict:
        """Convert NetworkX graph to dictionary format"""
        nodes = []
        for node_id, data in graph.nodes(data=True):
            node_type = data.get('node_type', '')
            type_name = "Join" if ("Join" in node_type or "Nest" in node_type) else \
                "Scan" if "Scan" in node_type else "Unknown"

            nodes.append({
                "id": node_id,
                "join_or_scan": type_name,
                "type": node_type,
                "cost": data.get('cost', -1),
                "isLeaf": len(list(graph.neighbors(node_id))) == 0,
                "conditions": data.get('conditions', []),
                "tables": sorted(list(data.get('tables', set()))),
                "isRoot": data.get('is_root', False)
            })

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