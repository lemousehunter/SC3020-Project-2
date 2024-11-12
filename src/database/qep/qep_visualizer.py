import networkx as nx
import matplotlib.pyplot as plt
from textwrap import wrap


class QEPVisualizer:
    def __init__(self, graph):
        """
        Initialize the QEP visualizer with a NetworkX graph.

        Args:
            graph: NetworkX graph representing the simplified query execution plan
        """
        self.graph = graph

    def _calculate_layout(self, root, width=1.2, height=1.):
        """
        Create a hierarchical layout with equidistant children and centered parents.

        Args:
            root: Root node of the tree
            width: Horizontal space between sibling nodes
            height: Vertical space between levels

        Returns:
            Dictionary of node positions
        """
        pos = {}

        def _get_tree_size(node, seen=None):
            """Calculate the number of leaf nodes in the subtree."""
            if seen is None:
                seen = set()
            if node in seen:
                return 0
            seen.add(node)
            children = list(self.graph.neighbors(node))
            if not children:
                return 1
            return sum(_get_tree_size(child, seen) for child in children)

        def _assign_positions(node, x=0, level=0, seen=None):
            """Assign x positions to all nodes."""
            if seen is None:
                seen = set()
            if node in seen:
                return x
            seen.add(node)

            children = list(self.graph.neighbors(node))
            start_x = x

            # Process children
            for child in children:
                if child not in seen:
                    x = _assign_positions(child, x, level + 1, seen)

            # Position current node
            if children:
                # Center parent above children
                children_x = [pos[child][0] for child in children]
                pos[node] = (sum(children_x) / len(children), -level)
            else:
                pos[node] = (x, -level)
                x += width

            return x

        # Assign initial positions
        _assign_positions(root)

        # Center the layout
        if pos:
            min_x = min(x for x, y in pos.values())
            max_x = max(x for x, y in pos.values())
            center_offset = (max_x + min_x) / 2
            scale = 2.0 / (max_x - min_x) if max_x > min_x else 1

            # Scale and center the positions
            pos = {node: ((x - center_offset) * scale, y * height)
                   for node, (x, y) in pos.items()}

        return pos

    def _format_value(self, value) -> str:
        """Format a value for display, handling different types appropriately."""
        if isinstance(value, (list, set)):
            return ', '.join(str(v) for v in value)
        elif isinstance(value, float):
            return f"{value:.2f}"
        elif isinstance(value, (dict, tuple)):
            return str(value)
        return str(value)

    def _format_node_attributes(self, attributes: dict) -> str:
        """Format all node attributes except those starting with '_' and node_type."""
        formatted_attrs = []

        # Get node type first (it will be displayed separately)
        node_type = attributes.get('node_type', 'Unknown')

        # Format remaining attributes
        for key, value in sorted(attributes.items()):
            # Skip private attributes and node_type
            if not key.startswith('_') and key != 'node_type':
                formatted_value = self._format_value(value)
                if formatted_value:  # Only include non-empty values
                    formatted_line = f"{key}: {formatted_value}"
                    # Wrap long lines
                    wrapped_lines = wrap(formatted_line, width=30)
                    formatted_attrs.extend(wrapped_lines)

        # Combine node type and other attributes
        return f"{node_type}\n" + ('-' * 20) + '\n' + '\n'.join(formatted_attrs)

    def visualize(self, output_file: str = 'qep_tree.png'):
        """
        Visualize the simplified query plan tree and save it to a file.
        Shows node type as title, followed by all other non-private attributes.

        Args:
            output_file: Path where the visualization should be saved
        """
        # Increase figure size to accommodate attributes
        plt.figure(figsize=(20, 15))

        # Find root node (node with is_root=True)
        root = [n for n, d in self.graph.nodes(data=True) if d.get('is_root', False)][0]

        # Calculate positions with increased spacing
        pos = self._calculate_layout(root, width=1.5)

        # Draw nodes with different colors for root vs non-root
        root_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('is_root', False)]
        non_root_nodes = [n for n, d in self.graph.nodes(data=True) if not d.get('is_root', False)]

        # Increase node size to accommodate more text
        node_size = 5000

        # Draw root node in a different color
        nx.draw_networkx_nodes(self.graph, pos,
                               nodelist=root_nodes,
                               node_size=node_size,
                               node_color='lightcoral',
                               node_shape='s')

        # Draw other nodes
        nx.draw_networkx_nodes(self.graph, pos,
                               nodelist=non_root_nodes,
                               node_size=node_size,
                               node_color='lightblue',
                               node_shape='s')

        # Draw edges
        nx.draw_networkx_edges(self.graph, pos,
                               edge_color='gray',
                               arrows=True,
                               arrowsize=20)

        # Create labels with all attributes
        labels = {
            node: self._format_node_attributes(data)
            for node, data in self.graph.nodes(data=True)
        }

        # Add labels with smaller font size and better wrapping
        nx.draw_networkx_labels(self.graph, pos,
                                labels,
                                font_size=8,
                                verticalalignment='center',
                                horizontalalignment='center',
                                bbox=dict(facecolor='white',
                                          edgecolor='none',
                                          alpha=0.7,
                                          pad=4.0))

        plt.title('Query Execution Plan Tree')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, bbox_inches='tight', dpi=300,
                    facecolor='white', edgecolor='none')
        plt.close()