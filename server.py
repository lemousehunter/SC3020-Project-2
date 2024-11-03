from flask import Flask, jsonify, request
from flask_cors import CORS
from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_modifier import QEPModifier
from src.database.query_modifier import QueryModifier
from src.types.qep_types import NodeType, QueryModification, JoinType, ScanType
from src.database.hint_generator import HintConstructor
from enum import Enum
from typing import Set
import networkx as nx
import uuid

app = Flask(__name__)
CORS(app)

# Store active database connection
active_db_connection = None

@app.route('/api/database/available', methods=['GET'])
def get_available_databases():
    """Get list of available databases"""
    try:
        # Hardcoded database list as per the API spec
        databases = [
            {"value": "TPC-H", "label": "TPC-H"},
            {"value": "mysql", "label": "MySQL"},
            {"value": "oracle", "label": "Oracle"},
            {"value": "sqlserver", "label": "SQL Server"}
        ]
        return jsonify({"databases": databases}), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/database/select', methods=['POST'])
def select_database():
    """Select and connect to a database"""
    try:
        if not request.is_json:
            return jsonify({
                "status": "error",
                "message": "Content-Type must be application/json"
            }), 400

        data = request.get_json()
        selected_db = data.get('database')

        if not selected_db:
            return jsonify({
                "status": "error",
                "message": "Database not specified"
            }), 400

        # Validate database selection
        valid_dbs = ["TPC-H", "mysql", "oracle", "sqlserver"]
        if selected_db not in valid_dbs:
            return jsonify({
                "status": "error",
                "message": "Database configuration not found"
            }), 400

        try:
            # Create new database connection and store it
            global active_db_connection
            active_db_connection = DatabaseManager(selected_db)
            try_query = active_db_connection.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")

            return jsonify({
                "status": "success",
                "message": f"Connected to {selected_db}",
                "selectedDatabase": selected_db,
                "Query result": try_query
            }), 200

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": "Database configuration not found"
            }), 400

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/query/plan', methods=['POST'])
def get_query_plan():
    """Get the original query execution plan"""
    try:    
        if not request.is_json:
            return jsonify({
                "status": "error",
                "message": "Content-Type must be application/json"
            }), 400

        data = request.get_json()
        query = data.get('query')

        if not query:
            return jsonify({
                "status": "error",
                "message": "Query is required"
            }), 400

        if not active_db_connection:
            return jsonify({
                "status": "error",
                "message": "No database connection"
            }), 400

        # Get QEP data
        qep_data = active_db_connection.get_qep(query)
        
        # Parse QEP into graph using updated parser
        parser = QEPParser()

        # to standardise format
        graph = parser.parse(qep_data)
        
        # Convert graph to networkx format for frontend
        nodes = []
        for node_id, data in graph.nodes(data=True):
            node_type = data.get('node_type', '')
            if "Join" in node_type or "Nest" in node_type:
                type_name = "Join"
            elif "Scan" in node_type:
                type_name = "Scan"
            else:
                type_name = "Unknown"

            node_info = {
                "id": node_id,
                "join_or_scan": type_name,
                "type": node_type,
                "cost": data.get('cost', -1),  # Use actual node cost instead of always using Hash Join cost
                "isLeaf": len(list(graph.neighbors(node_id))) == 0,
                "conditions": data.get('conditions', []),
                "tables": sorted(list(data.get('tables', set())))
            }

            nodes.append(node_info)

        edges = [{"source": u, "target": v} for u, v in graph.edges()]

        # Get total cost from root node
        root_nodes = [n for n, d in graph.nodes(data=True) if d.get('is_root', False)]
        total_cost = graph.nodes[root_nodes[0]]['cost'] if root_nodes else 0

        return jsonify({
            "status": "success",
            "message": "Query plan generated successfully",
            "sql_query": query,
            "cost": total_cost,
            "networkx_object": {
                "nodes": nodes,
                "edges": edges
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
@app.route('/api/query/modify', methods=['POST'])
def modify_query():
    try:
        if not request.is_json:
            return jsonify({
                "status": "error",
                "message": "Content-Type must be application/json"
            }), 400

        data = request.get_json()
        query = data.get('query')
        modifications = data.get('modifications', [])

        if not query:
            return jsonify({
                "status": "error",
                "message": "Query is required"
            }), 400

        if not active_db_connection:
            return jsonify({
                "status": "error",
                "message": "No database connection"
            }), 400

        # Get original QEP
        qep_data = active_db_connection.get_qep(query)
        
        # Parse QEP into graph
        parser = QEPParser()
        original_graph: nx.DiGraph = parser.parse(qep_data)
        original_cost = parser.get_total_cost()
        
        # Process modifications
        qep_modifier = QEPModifier(original_graph)
        for mod in modifications:
            try:
                node_type_str = mod.get('node_type')
                if not node_type_str:
                    raise ValueError("node_type is required")
                
                node_type = NodeType[node_type_str]
                tables = set(mod.get('tables', []))
                
                query_mod = QueryModification(
                    node_type=node_type,
                    original_type=mod.get('original_type'),
                    new_type=mod.get('new_type'),
                    tables=tables,
                    node_id=mod.get('node_id', '')
                )
                qep_modifier.add_modification(query_mod)
                
            except KeyError:
                return jsonify({
                    "status": "error",
                    "message": f"Invalid node_type: {node_type_str}. Must be one of {[e.name for e in NodeType]}"
                }), 400
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": f"Error processing modification: {str(e)}"
                }), 400

        # Get new QEP with modifications
        modified_graph: nx.DiGraph = qep_modifier.apply_modifications()

        hints = HintConstructor(modified_graph).generate_hints(query)
        modified_query = QueryModifier(
            query=query,
            hint=hints
        ).modify()

        updated_qep = active_db_connection.get_qep(modified_query)

        updated_graph = parser.parse(updated_qep)
        modified_cost = parser.get_total_cost()

        # Extract node information
        nodes = []
        for node_id, data in modified_graph.nodes(data=True):
            node_type = data.get('node_type', '')
            if "Join" in node_type or "Nest" in node_type:
                type_name = "Join"
            elif "Scan" in node_type:
                type_name = "Scan"
            else:
                type_name = "Unknown"

            node_info = {
                "id": node_id,
                "join_or_scan": type_name,
                "type": node_type,
                "cost": data.get('cost', -1),  # Use actual node cost instead of always using Hash Join cost
                "isLeaf": len(list(modified_graph.neighbors(node_id))) == 0,
                "conditions": data.get('conditions', []),
                "tables": sorted(list(data.get('tables', set())))
            }

            nodes.append(node_info)

        edges = [{"source": u, "target": v} for u, v in updated_graph.edges()]

        return jsonify({
            "status": "success",
            "message": "QEP modifications applied successfully",
            "modified_sql_query": query,
            "cost_comparison": {
                "original_cost": original_cost,
                "modified_cost": modified_cost
            },
            "updated_networkx_object": {
                "nodes": nodes,
                "edges": edges
            }
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)