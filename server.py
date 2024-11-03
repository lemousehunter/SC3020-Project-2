from flask import Flask, jsonify, request
from flask_cors import CORS
from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_modifier import QEPModifier
from src.database.query_modifier import QueryModifier
from src.types.qep_types import NodeType, QueryModification
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
            node_info = {
                "id": node_id,
                "type": data.get('node_type', ''),
                "cost": data.get('cost', 0),
                "isLeaf": len(list(graph.neighbors(node_id))) == 0,
                "conditions": data.get('conditions', []),
                "tables": sorted(data.get('tables', [])),
            }
            # Only add table if there's exactly one table
            if len(node_info["tables"]) == 1:
                node_info["table"] = node_info["tables"][0]
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
        original_cost = qep_data[0][0][0]['Plan']['Total Cost']
        
        # Parse QEP into graph
        modified_graph = nx.DiGraph()
        plan = qep_data[0][0][0]['Plan']
        
        def parse_qep_node(plan, graph, parent_id=None):
            """
            Recursively parse QEP nodes and build the graph structure
            """
            node_id = str(uuid.uuid4())
            
            # Extract basic node information
            node_type = plan.get('Node Type', '')
            total_cost = plan.get('Total Cost', -1)
            
            # Initialize node data
            node_data = {
                'node_type': node_type,
                'cost': total_cost,
                'conditions': [],
                'tables': set()
            }
            
            # Extract table information
            if 'Relation Name' in plan:
                node_data['tables'].add(plan['Relation Name'])
            
            # Extract join conditions
            if 'Hash Cond' in plan:
                node_data['conditions'].append(plan['Hash Cond'])
            
            # Add node to graph
            graph.add_node(node_id, **node_data)
            
            # Connect to parent if exists
            if parent_id:
                graph.add_edge(parent_id, node_id)
            
            # Recursively process child plans
            if 'Plans' in plan:
                for child_plan in plan['Plans']:
                    parse_qep_node(child_plan, graph, node_id)
            
            return node_id
        
        # Parse the initial QEP
        parse_qep_node(plan, modified_graph)
        
        # Process modifications
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
                
                # Apply modification logic here if needed
                
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
        modified_qep = active_db_connection.get_qep(query)
        modified_cost = modified_qep[0][0][0]['Plan']['Total Cost']

        # Extract node information
        nodes = []
        for node_id, data in modified_graph.nodes(data=True):
            node_info = {
                "id": node_id,
                "type": data.get('node_type', ''),
                "cost": data.get('cost', -1),  # Use actual node cost instead of always using Hash Join cost
                "isLeaf": len(list(modified_graph.neighbors(node_id))) == 0,
                "conditions": data.get('conditions', []),
                "tables": sorted(list(data.get('tables', set())))
            }
            if len(node_info["tables"]) == 1:
                node_info["table"] = node_info["tables"][0]
            nodes.append(node_info)

        edges = [{"source": u, "target": v} for u, v in modified_graph.edges()]

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