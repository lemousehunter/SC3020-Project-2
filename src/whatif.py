### QEP Editor
from typing import Dict, List, Optional, Tuple
import json
import copy

class QueryPlanModifier:
    """Handles modifications to query execution plans"""
    
    def __init__(self):
        self.valid_operators = {
            'scan': ['Seq Scan', 'Index Scan', 'Bitmap Scan'],
            'join': ['Hash Join', 'Merge Join', 'Nested Loop'],
            'aggregation': ['HashAggregate', 'GroupAggregate']
        }

    def modify_operator(self, plan: Dict, old_operator: str, new_operator: str,
                       node_id: Optional[str] = None) -> Dict:
        """Modify a specific operator in the query plan"""
        modified_plan = plan.copy()

        def traverse_and_modify(node: Dict) -> None:
            if isinstance(node, dict):
                if "Node Type" in node:
                    if node["Node Type"] == old_operator:
                        if node_id is None or ("Node Id" in node and node["Node Id"] == node_id):
                            node["Node Type"] = new_operator
                for key, value in node.items():
                    if isinstance(value, (dict, list)):
                        traverse_and_modify(value)
            elif isinstance(node, list):
                for item in node:
                    traverse_and_modify(item)

        traverse_and_modify(modified_plan)
        return modified_plan
    
    def extract_join_info(self, node: Dict) -> Tuple[List[Dict], set[Tuple[str, str]], Dict[str, List[Dict]]]:
        """
        Extracts join nodes, base relations, and the node hierarchy from a plan node.
        
        Args:
            node: Plan node to analyze
            
        Returns:
            Tuple of (join_nodes, relations, node_hierarchy)
            node_hierarchy maps each relation to its ancestor nodes in order from root to leaf
        """
        join_nodes = []
        relations = set()
        node_hierarchy = {}  # Maps relation name to list of ancestor nodes
        
        def traverse(current_node: Dict, ancestors: List[Dict] = None) -> None:
            if ancestors is None:
                ancestors = []
                
            if isinstance(current_node, dict):
                current_ancestors = ancestors + [current_node]
                
                if "Node Type" in current_node:
                    if any(join in current_node["Node Type"] for join in self.valid_operators['join']):
                        join_nodes.append(current_node)
                    if "Relation Name" in current_node:
                        relation_name = current_node["Relation Name"]
                        relations.add((
                            relation_name,
                            current_node.get("Alias", "")
                        ))
                        # Store the full ancestor chain for this relation
                        node_hierarchy[relation_name] = [
                            copy.deepcopy(node) for node in current_ancestors[:-1]
                        ]
                
                # Traverse child nodes
                for key, value in current_node.items():
                    if isinstance(value, (dict, list)):
                        traverse(value, current_ancestors)
            elif isinstance(current_node, list):
                for item in current_node:
                    traverse(item, ancestors)
                    
        traverse(node)
        return join_nodes, relations, node_hierarchy

    def find_relation_node(self, rel_name: str, node: Dict, node_hierarchy: Dict[str, List[Dict]]) -> Optional[Dict]:
        """
        Finds the node for a given relation in the plan and reconstructs its node hierarchy.
        
        Args:
            rel_name: Name of the relation to find
            node: Plan node to search in
            node_hierarchy: Map of ancestor nodes by relation name
            
        Returns:
            The found node with its hierarchy reconstructed, or None
        """
        def find_base_node(current_node: Dict) -> Optional[Dict]:
            if isinstance(current_node, dict):
                if current_node.get("Relation Name") == rel_name:
                    return copy.deepcopy(current_node)
                for value in current_node.values():
                    if isinstance(value, (dict, list)):
                        result = find_base_node(value)
                        if result:
                            return result
            elif isinstance(current_node, list):
                for item in current_node:
                    result = find_base_node(item)
                    if result:
                        return result
            return None

        base_node = find_base_node(node)
        if not base_node:
            return None

        # If this relation has ancestor nodes, reconstruct the hierarchy
        if rel_name in node_hierarchy and node_hierarchy[rel_name]:
            current_node = base_node
            for ancestor in reversed(node_hierarchy[rel_name]):
                wrapper = copy.deepcopy(ancestor)
                wrapper["Plans"] = [current_node]
                current_node = wrapper
            return current_node
        
        return base_node

    def build_join_tree(self, join_order: List[str], original_plan: Dict,
                    join_nodes: List[Dict], node_hierarchy: Dict[str, List[Dict]]) -> Dict:
        """
        Builds a new join tree based on the specified join order.
        
        Args:
            join_order: List of relation names in desired order
            original_plan: Original query plan
            join_nodes: List of join nodes from original plan
            node_hierarchy: Map of ancestor nodes by relation name
            
        Returns:
            New plan with reordered joins
        """
        # Find base relation nodes with their hierarchies
        nodes = []
        for rel in join_order:
            node = self.find_relation_node(rel, original_plan, node_hierarchy)
            if node:
                nodes.append(node)
            else:
                raise ValueError(f"Relation {rel} not found in plan")

        # Build join tree bottom-up
        join_template = next((node for node in join_nodes), None)
        if not join_template:
            raise ValueError("No join nodes found in original plan")

        def create_join_node(left: Dict, right: Dict, template: Dict) -> Dict:
            """Creates a new join node connecting two subtrees"""
            join_node = copy.deepcopy(template)
            
            # Clear any existing plans and conditions
            join_node = {k: v for k, v in join_node.items() 
                        if k not in ("Plans", "Hash Cond", "Index Cond", "Merge Cond")}
            
            join_node["Plans"] = [left, right]
            
            # Update parent relationships
            left["Parent Relationship"] = "Outer"
            right["Parent Relationship"] = "Inner"
            
            return join_node

        while len(nodes) > 1:
            left = nodes.pop(0)
            right = nodes.pop(0)
            new_join = create_join_node(left, right, join_template)
            nodes.insert(0, new_join)

        return nodes[0]

    def modify_join_order(self, plan: Dict, join_order: List[str]) -> Dict:
        """
        Modifies the join order in a query execution plan while preserving node hierarchies.
        
        Args:
            plan: Original query execution plan
            join_order: List of relation names in desired join order
            
        Returns:
            Modified plan with new join order
        """
        # Extract join information and node hierarchies from original plan
        join_nodes, relations, node_hierarchy = self.extract_join_info(plan["Plan"])
        
        # Validate join order
        relation_names = {rel[0] for rel in relations}
        if set(join_order) != relation_names:
            raise ValueError(
                f"Join order must contain exactly the relations in the plan.\n"
                f"Expected: {relation_names}\n"
                f"Got: {set(join_order)}"
            )
        
        # Create new plan with modified join order
        modified_plan = copy.deepcopy(plan)
        modified_plan["Plan"] = self.build_join_tree(
            join_order,
            plan["Plan"],
            join_nodes,
            node_hierarchy
        )
        
        return modified_plan

def print_join_order(plan: Dict, indent: int = 0) -> None:
    """Helper function to print the join order in a readable format"""
    if isinstance(plan, dict):
        if "Plan" in plan:
            print_join_order(plan["Plan"], indent)
            return
            
        node_type = plan.get("Node Type", "")
        relation = plan.get("Relation Name", "")
        alias = plan.get("Alias", "")
        
        indent_str = "  " * indent
        node_info = f"{indent_str}{node_type}"
        if relation:
            node_info += f" on {relation}"
            if alias:
                node_info += f" ({alias})"
        print(node_info)
        
        if "Plans" in plan:
            for child in plan["Plans"]:
                print_join_order(child, indent + 1)

class SQLGenerator:
    """Generates and executes modified SQL queries based on query plan changes"""
    
    def _extract_tables_from_plan(self, plan: Dict) -> List[Tuple[str, str]]:
        """Extract table names and aliases from a query plan"""
        tables = []
        
        def traverse(node: Dict):
            if isinstance(node, dict):
                if "Node Type" in node and "Relation Name" in node:
                    table_name = node["Relation Name"].lower()
                    alias = node.get("Alias", table_name)
                    tables.append((table_name, alias))
                    
                if "Plans" in node:
                    for child in node["Plans"]:
                        traverse(child)
                        
        if "Plan" in plan:
            traverse(plan["Plan"])
        else:
            traverse(plan)
            
        return tables

    def _extract_join_conditions(self, plan: Dict) -> List[str]:
        """Extract join conditions from a query plan"""
        conditions = []
        
        def traverse(node: Dict):
            if isinstance(node, dict):
                for cond_type in ["Hash Cond", "Merge Cond", "Index Cond"]:
                    if cond_type in node:
                        cond = node[cond_type].strip("()")
                        conditions.append(cond)
                
                if "Plans" in node:
                    for child in node["Plans"]:
                        traverse(child)
                        
        if "Plan" in plan:
            traverse(plan["Plan"])
        else:
            traverse(plan)
            
        return conditions

    def _extract_join_algorithm(self, plan: Dict) -> str:
        """Extract the join algorithm used in the original plan"""
        def traverse(node: Dict) -> Optional[str]:
            if isinstance(node, dict):
                if "Node Type" in node and "Join" in node["Node Type"]:
                    return node["Node Type"]
                    
                if "Plans" in node:
                    for child in node["Plans"]:
                        result = traverse(child)
                        if result:
                            return result
            return None
            
        if "Plan" in plan:
            return traverse(plan["Plan"])
        return traverse(plan)

    def _get_join_settings(self, join_type: str) -> str:
        """Generate appropriate SET commands to maintain the join algorithm"""
        if join_type == "Nested Loop":
            return """
            SET LOCAL enable_hashjoin = off;
            SET LOCAL enable_mergejoin = off;
            SET LOCAL enable_nestloop = on;"""
        elif join_type == "Hash Join":
            return """
            SET LOCAL enable_hashjoin = on;
            SET LOCAL enable_mergejoin = off;
            SET LOCAL enable_nestloop = off;"""
        elif join_type == "Merge Join":
            return """
            SET LOCAL enable_hashjoin = off;
            SET LOCAL enable_mergejoin = on;
            SET LOCAL enable_nestloop = off;"""
        return ""  # Default case - let PostgreSQL decide

    def _extract_limit(self, original_query: str) -> Optional[str]:
        """Extract LIMIT clause if present in original query"""
        query_upper = original_query.upper()
        if "LIMIT" in query_upper:
            limit_idx = query_upper.find("LIMIT")
            limit_clause = original_query[limit_idx:]
            return limit_clause
        return None

    def _generate_core_query(self, plan: Dict, modifications: List[Dict]) -> str:
        """Generate the core SELECT query without transaction wrapping"""
        tables = self._extract_tables_from_plan(plan)
        conditions = self._extract_join_conditions(plan)
        table_map = {table.lower(): alias for table, alias in tables}
        
        # Get join order from modifications
        join_order = None
        for mod in modifications:
            if mod['type'] == 'join_order_change':
                join_order = [name.lower() for name in mod['new_join_order']]
                break
        
        if not join_order:
            join_order = [table for table, _ in tables]
        
        # Build the Leading hint
        leading_hint = f"/*+ Leading({' '.join(table_map[t] for t in join_order)}) */"
        
        # Build FROM clause
        from_parts = []
        for table_name in join_order:
            alias = table_map.get(table_name, table_name)
            if alias != table_name:
                from_parts.append(f"{table_name} AS {alias}")
            else:
                from_parts.append(table_name)
                
        from_clause = ", ".join(from_parts)
        
        # Build WHERE clause
        where_conditions = []
        if conditions:
            where_conditions.extend(conditions)
            
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Core query
        query = f"SELECT {leading_hint} *\nFROM {from_clause}\nWHERE {where_clause}"
        
        # Add LIMIT if present in original query
        limit_clause = self._extract_limit(self.original_query) if hasattr(self, 'original_query') else None
        if limit_clause:
            query += f"\n{limit_clause}"
        
        return query

    def generate_modified_sql(self, original_query: str, modifications: List[Dict], plan: Dict) -> str:
        """Generate complete SQL with transaction and settings"""
        self.original_query = original_query  # Store for LIMIT extraction
        
        # Extract original join algorithm
        original_join_type = self._extract_join_algorithm(plan)
        
        # Get appropriate settings to maintain the join algorithm
        settings = self._get_join_settings(original_join_type) if original_join_type else ""
        
        # Generate core query with join order modifications
        core_query = self._generate_core_query(plan, modifications)
        
        # Combine settings and query
        if settings:
            return f"{settings}\n{core_query};"
        return f"{core_query};"

    def generate_explain_sql(self, original_query: str, modifications: List[Dict], plan: Dict) -> str:
        """Generate EXPLAIN query for the modified SQL"""
        self.original_query = original_query  # Store for LIMIT extraction
        modified_sql = self.generate_modified_sql(original_query, modifications, plan)
        return f"EXPLAIN (FORMAT JSON) {modified_sql}"
    
class CostAnalyzer:
    """Analyzes and compares costs of different query plans"""
    
    @staticmethod
    def extract_cost(plan: Dict) -> float:
        """Extract the total cost from a query plan"""
        return float(plan.get("Total Cost", 0))

    def compare_costs(self, original_plan: Dict, modified_plan: Dict) -> Dict:
        """Compare costs between original and modified plans"""
        original_cost = self.extract_cost(original_plan)
        modified_cost = self.extract_cost(modified_plan)
        
        difference = modified_cost - original_cost
        percentage = (difference / original_cost) * 100 if original_cost != 0 else float('inf')
        
        return {
            "original_cost": original_cost,
            "modified_cost": modified_cost,
            "difference": difference,
            "percentage_change": percentage,
            "is_improvement": difference < 0
        }

    def analyze_performance_factors(self, plan: Dict) -> Dict:
        """Analyze various performance factors in a query plan"""
        factors = {
            "total_cost": 0,
            "startup_cost": 0,
            "rows_processed": 0,
            "scan_types": [],
            "join_types": []
        }

        def traverse_plan(node: Dict) -> None:
            if isinstance(node, dict):
                if "Total Cost" in node:
                    factors["total_cost"] = max(factors["total_cost"], float(node["Total Cost"]))
                if "Startup Cost" in node:
                    factors["startup_cost"] = max(factors["startup_cost"], float(node["Startup Cost"]))
                if "Plan Rows" in node:
                    factors["rows_processed"] += int(node["Plan Rows"])
                if "Node Type" in node:
                    if "scan" in node["Node Type"].lower():
                        factors["scan_types"].append(node["Node Type"])
                    elif "join" in node["Node Type"].lower():
                        factors["join_types"].append(node["Node Type"])
                
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        traverse_plan(value)
            elif isinstance(node, list):
                for item in node:
                    traverse_plan(item)

        traverse_plan(plan)
        return factors