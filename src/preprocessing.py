import psycopg2
import json
from typing import Dict, List, Optional, Tuple
import copy

class DatabaseConnection:
    """Handles database connection and query execution"""
    def __init__(self, 
                 dbname: str = "TPC-H", 
                 user: str = "postgres",
                 password: str = "password", 
                 host: str = "localhost", 
                 port: str = "5432"):
        """Initialize database connection parameters"""
        self.connection_params = {
            "dbname": dbname,
            "user": user,
            "password": password,
            "host": host,
            "port": port
        }
        self.conn = None
        self.cur = None

    def connect(self) -> None:
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.connection_params)
            self.cur = self.conn.cursor()
            if self.cur is not None:
                print("Database connection successful")
        except Exception as e:
            raise Exception(f"Failed to connect to database: {str(e)}")

    def disconnect(self) -> None:
        """Close database connection"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()

    def execute_query(self, query: str) -> Tuple[List, Optional[str]]:
        """Execute SQL query and return results"""
        try:
            self.cur.execute(query)
            results = self.cur.fetchall()
            return results, None
        except Exception as e:
            return [], str(e)

class QueryPlanExtractor:
    """Extracts and processes query execution plans"""
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection

    def get_query_plan(self, sql_query: str) -> Dict:
        """Get the query execution plan for a given SQL query"""
        # Wrap the entire query (including SET statements) in EXPLAIN
        explain_query = f"EXPLAIN (FORMAT JSON) {sql_query}"
        results, error = self.db.execute_query(explain_query)
        
        if error:
            raise Exception(f"Failed to get query plan: {error}")
            
        return results[0][0][0] if results else {}

    def extract_operators(self, plan: Dict) -> List[str]:
        """Extract all operators from a query plan"""
        operators = []
        
        def traverse_plan(node):
            if isinstance(node, dict):
                if "Node Type" in node:
                    operators.append(node["Node Type"])
                for value in node.values():
                    traverse_plan(value)
            elif isinstance(node, list):
                for item in node:
                    traverse_plan(item)
        
        traverse_plan(plan)
        return operators

    def format_query_plan(self, qep_dict: Dict, indent: int = 4) -> str:
        """
        Format a query execution plan dictionary with proper indentation.
        
        Args:
            qep_dict (Dict): The query execution plan dictionary to format
            indent (int): Number of spaces for each indentation level
            
        Returns:
            str: A properly formatted string representation of the QEP
        """
        def _format_value(value: any, level: int) -> str:
            if isinstance(value, dict):
                return _format_dict(value, level)
            elif isinstance(value, list):
                return _format_list(value, level)
            elif isinstance(value, bool):
                return str(value)
            elif isinstance(value, (int, float)):
                return str(value)
            else:
                return f"'{value}'"

        def _format_dict(d: Dict, level: int) -> str:
            if not d:
                return "{}"
            
            lines = ["{"]
            for i, (key, value) in enumerate(d.items()):
                comma = "," if i < len(d) - 1 else ""
                formatted_value = _format_value(value, level + 1)
                lines.append(f"{' ' * (level + indent)}'{key}': {formatted_value}{comma}")
            lines.append(f"{' ' * level}}}")
            return "\n".join(lines)

        def _format_list(lst: List, level: int) -> str:
            if not lst:
                return "[]"
            
            lines = ["["]
            for i, item in enumerate(lst):
                comma = "," if i < len(lst) - 1 else ""
                formatted_item = _format_value(item, level + indent)
                lines.append(f"{' ' * (level + indent)}{formatted_item}{comma}")
            lines.append(f"{' ' * level}]")
            return "\n".join(lines)

        # Start the formatting with the outermost dictionary
        formatted_qep = "qep = " + _format_dict(qep_dict, 0)
        return formatted_qep

    def get_formatted_plan(self, sql_query: str, indent: int = 4) -> str:
        """
        Get a formatted query execution plan for a given SQL query.
        
        Args:
            sql_query (str): The SQL query to analyze
            indent (int): Number of spaces for indentation
            
        Returns:
            str: Formatted query execution plan
        """
        plan = self.get_query_plan(sql_query)
        return self.format_query_plan(plan, indent)

class SchemaAnalyzer:
    """Analyzes database schema for table and column information"""
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection

    def get_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """
        results, error = self.db.execute_query(query)
        return [r[0] for r in results] if not error else []

    def get_columns(self, table_name: str) -> List[str]:
        """Get list of columns for a specific table"""
        query = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
        """
        results, error = self.db.execute_query(query)
        return [r[0] for r in results] if not error else []

def parse_sql_query(query: str) -> Dict:
    """Parse SQL query to extract tables and conditions"""
    # This is a simplified parser - you might want to use a proper SQL parser
    query = query.lower()
    parsed = {
        "tables": [],
        "conditions": [],
        "selections": []
    }
    
    # Extract tables
    if "from" in query:
        from_part = query.split("from")[1].split("where")[0]
        parsed["tables"] = [t.strip() for t in from_part.split(",")]
    
    # Extract conditions
    if "where" in query:
        where_part = query.split("where")[1]
        parsed["conditions"] = [c.strip() for c in where_part.split("and")]
    
    return parsed