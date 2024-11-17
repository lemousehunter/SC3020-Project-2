from multiprocessing import Process

from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass
from src.database.databaseManager import DatabaseManager
from src.interface import run_interface

from src.utils.JSONEncoder import SetEncoder
from src.whatif import QueryPlanManager


@dataclass
class DatabaseConfig:
    """Configuration for available databases"""
    name: str
    value: str


class DatabaseServer:
    """Main server class handling database operations and API endpoints"""

    def __init__(self):
        self.app = Flask(__name__)
        self.app.json = SetEncoder(self.app)
        CORS(self.app, resources={
            r"/api/*": {
                "origins": ["http://localhost:3001"],  # Your NextJS development server
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type"]
            }
        })
        self.db_connection: Optional[DatabaseManager] = None
        self.query_plan_manager = QueryPlanManager()
        self._register_routes()

    def _register_routes(self):
        """Register all API routes"""
        self.app.route('/api/database/available', methods=['GET'])(self.get_available_databases)
        self.app.route('/api/database/select', methods=['POST'])(self.select_database)
        self.app.route('/api/query/plan', methods=['POST'])(self.get_query_plan)
        self.app.route('/api/query/modify', methods=['POST'])(self.modify_query)
        self.app.route('/api/preview_join_swaps', methods=['POST'])(self.preview_join_swaps)

    def preview_join_swaps(self):
        """Preview join swaps based on modifications"""
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

        data = request.get_json()
        modifications = data.get('modifications', [])

        try:
            modified_graph_json = self.query_plan_manager.preview_swap(modifications)
            return jsonify({
                "status": "success",
                "message": "Preview join swaps successful",
                "networkx_object": modified_graph_json,
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
                "hints": result["hints"],
                "changes_lst": result['changes_lst']
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def run(self, debug: bool = True, port: int = 5000):
        """Run the Flask server"""
        self.app.run(debug=debug, port=port)


if __name__ == '__main__':
    p1 = Process(target=run_interface)
    p1.start()
    server = DatabaseServer()
    server.run(debug=True, port=5000)
