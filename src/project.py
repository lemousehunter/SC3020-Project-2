import tkinter as tk
from typing import Dict, Optional
import json
import sys

from preprocessing import DatabaseConnection, QueryPlanExtractor, SchemaAnalyzer
from whatif import QueryPlanModifier, SQLGenerator, CostAnalyzer
from interface import Application

class QueryPlanAnalyzer:
    """Main application controller"""
    
    def __init__(self):
        # Initialize database connection
        self.db_conn = DatabaseConnection()
        try:
            self.db_conn.connect()
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            sys.exit(1)

        # Initialize components
        self.plan_extractor = QueryPlanExtractor(self.db_conn)
        self.schema_analyzer = SchemaAnalyzer(self.db_conn)
        self.plan_modifier = QueryPlanModifier()
        self.sql_generator = SQLGenerator()
        self.cost_analyzer = CostAnalyzer()
        
        # Initialize UI
        self.root = tk.Tk()
        self.app = Application(self.root)
        
        # Set up callbacks
        self.setup_callbacks()
        
        # Store current state
        self.current_query: Optional[str] = None
        self.current_plan: Optional[Dict] = None
        self.modified_plan: Optional[Dict] = None

    def setup_callbacks(self) -> None:
        """Set up UI callbacks"""
        self.app.visualizer.analyze_button.config(command=self.analyze_query)
        self.app.visualizer.set_on_modify_callback(self.modify_plan)

    def analyze_query(self) -> None:
        """Analyze the current SQL query"""
        query = self.app.visualizer.query_text.get('1.0', tk.END).strip()
        if not query:
            return

        try:
            # Get query plan
            self.current_query = query
            self.current_plan = self.plan_extractor.get_query_plan(query)
            
            # Visualize plan
            self.app.visualizer.visualize_plan(self.current_plan)
            
            # Reset cost comparison
            self.app.visualizer.cost_text.delete('1.0', tk.END)
            
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to analyze query: {str(e)}")

    def modify_plan(self, old_operator: str, new_operator: str) -> None:
        """Handle plan modifications"""
        try:
            # Modify the plan
            self.modified_plan = self.plan_modifier.modify_operator(
                self.current_plan, old_operator, new_operator)
            
            # Generate modified SQL
            modifications = [{
                'type': 'operator_change',
                'old_operator': old_operator,
                'new_operator': new_operator
            }]
            modified_sql = self.sql_generator.generate_modified_sql(
                self.current_query, modifications)
            
            # Get new plan and costs
            new_plan = self.plan_extractor.get_query_plan(modified_sql)
            cost_comparison = self.cost_analyzer.compare_costs(
                self.current_plan, new_plan)
            
            # Update visualization
            self.app.visualizer.visualize_plan(new_plan)
            self.app.visualizer.update_cost_comparison(cost_comparison)
            
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to modify plan: {str(e)}")

    def run(self) -> None:
        """Run the application"""
        try:
            self.app.run()
        finally:
            self.db_conn.disconnect()

def format_query_plan(plan, level=0):
    """Format a PostgreSQL query plan with proper indentation."""
    def indent(level):
        return "  " * level

    def format_node(node, level):
        output = []
        
        # Format the current node
        output.append(f"{indent(level)}Node: {node['Node Type']}")
        
        # Add important properties
        for key, value in node.items():
            if key in ['Node Type', 'Plans']:  # Skip these as they're handled separately
                continue
            output.append(f"{indent(level + 1)}{key}: {value}")
        
        # Recursively format child plans
        if 'Plans' in node:
            output.append(f"{indent(level)}Subplans:")
            for child in node['Plans']:
                output.extend(format_node(child, level + 1))
        
        return output

    # Start formatting from the root plan
    lines = format_node(plan['Plan'], level)
    return '\n'.join(lines)

def main():
    """
    Main entry point for the query plan analysis tool.
    Demonstrates modifying join orders and comparing query plans.
    """
    try:
        # Initialize components
        db_conn = DatabaseConnection()
        db_conn.connect()
        
        query_extractor = QueryPlanExtractor(db_conn)
        plan_modifier = QueryPlanModifier()
        sql_generator = SQLGenerator()
        cost_analyzer = CostAnalyzer()

        # Original query with nested loop join
        original_query = """
            SELECT * 
            FROM orders O, customer C
            WHERE O.O_CUSTKEY = C.C_CUSTKEY 
            LIMIT 10
        """
        print("\n=== Original Query ===")
        print(original_query.strip())
        
        # Get original plan
        original_plan = query_extractor.get_query_plan(original_query)
        print("\n=== Original Query Plan ===")
        print(format_query_plan(original_plan))

        # Define new join order
        new_join_order = ['customer', 'orders']
        modifications = [{
            'type': 'join_order_change',
            'new_join_order': new_join_order
        }]
        
        # Generate modified SQL that preserves join algorithm
        modified_sql = sql_generator.generate_modified_sql(original_query, modifications, original_plan)
        print("\n=== Generated Modified SQL ===")
        print(modified_sql)

        # Get new plan and compare
        new_plan = query_extractor.get_query_plan(modified_sql)
        print("\n=== Modified Query Plan ===")
        print(format_query_plan(new_plan))

        # Compare costs
        cost_comparison = cost_analyzer.compare_costs(original_plan, new_plan)
        print("\n=== Cost Comparison ===")
        print(f"Original Cost: {cost_comparison['original_cost']:.2f}")
        print(f"Modified Cost: {cost_comparison['modified_cost']:.2f}")
        print(f"Difference: {cost_comparison['difference']:.2f}")
        print(f"Percentage Change: {cost_comparison['percentage_change']:.2f}%")
        print(f"Is Improvement: {cost_comparison['is_improvement']}")

    except Exception as e:
        print(f"\nError: {str(e)}")
        raise
    
    finally:
        if 'db_conn' in locals():
            db_conn.disconnect()

if __name__ == "__main__":
    main()