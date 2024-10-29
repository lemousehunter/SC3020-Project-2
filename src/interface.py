import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
from typing import Dict, List, Optional, Callable
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backend_bases import MouseEvent

class QueryPlanVisualizer:
    """Visualizes query execution plans as interactive trees"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.setup_ui()
        self.graph = nx.DiGraph()
        self.pos = None
        self.selected_node = None
        self.original_plan = None
        self.modified_plan = None
        self.on_modify_callback = None

    def setup_ui(self) -> None:
        """Setup the main UI components"""
        self.root.title("Query Plan Analyzer")
        
        # Create main frames
        self.left_frame = ttk.Frame(self.root, padding="5")
        self.right_frame = ttk.Frame(self.root, padding="5")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Query input
        self.query_frame = ttk.LabelFrame(self.left_frame, text="SQL Query", padding="5")
        self.query_frame.pack(fill=tk.BOTH, expand=True)
        
        self.query_text = scrolledtext.ScrolledText(self.query_frame, height=10)
        self.query_text.pack(fill=tk.BOTH, expand=True)
        
        # Button frame
        self.button_frame = ttk.Frame(self.left_frame, padding="5")
        self.button_frame.pack(fill=tk.X)
        
        self.analyze_button = ttk.Button(self.button_frame, text="Analyze Query")
        self.analyze_button.pack(side=tk.LEFT, padx=5)
        
        # Plan visualization
        self.plan_frame = ttk.LabelFrame(self.right_frame, text="Query Plan", padding="5")
        self.plan_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create matplotlib figure
        self.figure, self.ax = plt.subplots(figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plan_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Connect mouse events
        self.canvas.mpl_connect('button_press_event', self.on_node_click)

        # Operator modification frame
        self.mod_frame = ttk.LabelFrame(self.right_frame, text="Modify Operator", padding="5")
        self.mod_frame.pack(fill=tk.X)
        
        self.operator_var = tk.StringVar()
        self.operator_combo = ttk.Combobox(self.mod_frame, textvariable=self.operator_var)
        self.operator_combo.pack(side=tk.LEFT, padx=5)
        
        self.apply_button = ttk.Button(self.mod_frame, text="Apply Changes", command=self.apply_changes)
        self.apply_button.pack(side=tk.LEFT, padx=5)

        # Cost comparison frame
        self.cost_frame = ttk.LabelFrame(self.right_frame, text="Cost Comparison", padding="5")
        self.cost_frame.pack(fill=tk.X)
        
        self.cost_text = scrolledtext.ScrolledText(self.cost_frame, height=5)
        self.cost_text.pack(fill=tk.BOTH, expand=True)

    def set_on_modify_callback(self, callback: Callable) -> None:
        """Set callback for when modifications are made"""
        self.on_modify_callback = callback

    def visualize_plan(self, plan: Dict) -> None:
        """Visualize the query plan as an interactive tree"""
        self.graph.clear()
        self.ax.clear()
        self.original_plan = plan
        
        def add_nodes(node: Dict, parent_id: Optional[str] = None) -> str:
            node_id = str(id(node))
            node_type = node.get("Node Type", "Unknown")
            cost = node.get("Total Cost", 0)
            label = f"{node_type}\n(Cost: {cost})"
            self.graph.add_node(node_id, label=label, node_data=node)
            
            if parent_id:
                self.graph.add_edge(parent_id, node_id)
            
            if "Plans" in node:
                for child in node["Plans"]:
                    add_nodes(child, node_id)
            
            return node_id

        add_nodes(plan)
        
        # Position nodes using hierarchical layout
        self.pos = nx.spring_layout(self.graph)
        
        # Draw the graph
        nx.draw(self.graph, self.pos, ax=self.ax,
                with_labels=True,
                labels=nx.get_node_attributes(self.graph, 'label'),
                node_color='lightblue',
                node_size=3000,
                font_size=8)
        
        self.canvas.draw()

    def on_node_click(self, event: MouseEvent) -> None:
        """Handle node click events"""
        if event.inaxes != self.ax:
            return

        click_pos = (event.xdata, event.ydata)
        min_dist = float('inf')
        closest_node = None

        # Find the closest node to the click position
        for node_id, pos in self.pos.items():
            dist = ((pos[0] - click_pos[0])**2 + (pos[1] - click_pos[1])**2)**0.5
            if dist < min_dist:
                min_dist = dist
                closest_node = node_id

        if min_dist < 0.1:  # Threshold for considering a click as hitting a node
            self.select_node(closest_node)

    def select_node(self, node_id: str) -> None:
        """Handle node selection"""
        self.selected_node = node_id
        node_data = self.graph.nodes[node_id]['node_data']
        node_type = node_data.get("Node Type", "Unknown")
        
        # Update operator combo box with valid alternatives
        valid_operators = self.get_valid_operators(node_type)
        self.operator_combo['values'] = valid_operators
        self.operator_combo.set(node_type)
        
        # Highlight selected node
        self.visualize_plan(self.original_plan)  # Redraw to clear previous highlights
        nx.draw_networkx_nodes(self.graph, self.pos,
                             nodelist=[node_id],
                             node_color='yellow',
                             node_size=3000)
        self.canvas.draw()

    def get_valid_operators(self, node_type: str) -> List[str]:
        """Get valid alternative operators for a given node type"""
        scan_ops = ['Seq Scan', 'Index Scan', 'Bitmap Scan']
        join_ops = ['Hash Join', 'Merge Join', 'Nested Loop']
        agg_ops = ['HashAggregate', 'GroupAggregate']
        
        if 'scan' in node_type.lower():
            return scan_ops
        elif 'join' in node_type.lower():
            return join_ops
        elif 'aggregate' in node_type.lower():
            return agg_ops
        return []

    def apply_changes(self) -> None:
        """Apply operator changes to the plan"""
        if not self.selected_node or not self.on_modify_callback:
            return
            
        new_operator = self.operator_var.get()
        if new_operator:
            node_data = self.graph.nodes[self.selected_node]['node_data']
            old_operator = node_data.get("Node Type", "Unknown")
            
            if new_operator != old_operator:
                self.on_modify_callback(old_operator, new_operator)

    def update_cost_comparison(self, cost_info: Dict) -> None:
        """Update the cost comparison display"""
        self.cost_text.delete('1.0', tk.END)
        
        cost_text = f"""Original Cost: {cost_info['original_cost']:.2f}
Modified Cost: {cost_info['modified_cost']:.2f}
Difference: {cost_info['difference']:.2f} ({cost_info['percentage_change']:.1f}%)
{'✓ Improvement' if cost_info['is_improvement'] else '✗ Regression'}"""
        
        self.cost_text.insert('1.0', cost_text)

class Application:
    """Main application class"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.geometry("1200x800")
        self.visualizer = QueryPlanVisualizer(root)
        
    def run(self) -> None:
        """Start the application"""
        self.root.mainloop()