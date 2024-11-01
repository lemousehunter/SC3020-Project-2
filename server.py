from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json
from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_modifier import QueryModifier
from src.database.qep.qep_visualizer import QEPVisualizer
from src.database.query_reconstruction import QueryConstructor

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
            {"value": "postgresql", "label": "PostgreSQL"},
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
        # Check content type
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
        valid_dbs = ["postgresql", "mysql", "oracle", "sqlserver"]
        if selected_db not in valid_dbs:
            return jsonify({
                "status": "error",
                "message": "Database configuration not found"
            }), 400

        try:
            # Create new database connection and store it
            global active_db_connection
            active_db_connection = DatabaseManager(selected_db)

            return jsonify({
                "status": "success",
                "message": f"Connected to {selected_db}",
                "selectedDatabase": selected_db
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

        # Get QEP
        qep_data = active_db_connection.get_qep(query)
        
        # Parse QEP into graph
        parser = QEPParser()
        graph = parser.parse(qep_data)
        
        # Convert graph to networkx format for frontend
        nodes = []
        for node_id, data in graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "type": data.get('node_type', ''),
                "table": list(data.get('tables', []))[0] if data.get('tables') and len(data.get('tables')) == 1 else None,
                "cost": data.get('cost', 0),
                "isLeaf": len(list(graph.neighbors(node_id))) == 0
            })

        edges = [{"source": u, "target": v} for u, v in graph.edges()]

        # Get total cost from root node
        total_cost = graph.nodes[list(graph.nodes)[0]]['cost']

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
    """Generate Alternative Query Plan"""
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
        original_graph = parser.parse(qep_data)
        
        # Apply modifications if any
        modifier = QueryModifier(original_graph)
        for mod in modifications:
            modifier.add_modification(mod)
        
        modified_graph = modifier.apply_modifications()
        
        # Generate new query
        constructor = QueryConstructor(modified_graph)
        modified_query = constructor.construct_query()
        
        # Get execution costs
        original_cost = original_graph.nodes[list(original_graph.nodes)[0]]['cost']
        modified_qep = active_db_connection.get_qep(modified_query)
        modified_cost = modified_qep[0][0][0]['Plan']['Total Cost']

        # Convert graph to networkx format for frontend
        nodes = []
        for node_id, data in modified_graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "type": data.get('node_type', ''),
                "table": list(data.get('tables', []))[0] if data.get('tables') and len(data.get('tables')) == 1 else None,
                "cost": data.get('cost', 0),
                "isLeaf": len(list(modified_graph.neighbors(node_id))) == 0
            })

        edges = [{"source": u, "target": v} for u, v in modified_graph.edges()]

        return jsonify({
            "status": "success",
            "message": "AQP generated successfully",
            "modified_sql_query": modified_query,
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