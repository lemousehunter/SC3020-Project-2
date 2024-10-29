import networkx as nx
import matplotlib.pyplot as plt


class QEPVisualizer:
    def __init__(self, graph):
        """
        Initialize the QEP visualizer with a NetworkX graph.

        Args:
            graph: NetworkX graph representing the query execution plan
        """
        self.graph = graph

    def _calculate_layout(self, root, width=1., height=1.):
        """
        Create a hierarchical layout with equidistant children and centered parents.

        Args:
            root: Root node of the tree
            width: Horizontal space between sibling nodes
            height: Vertical space between levels

        Returns:
            Dictionary of node positions
        """

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

        def _assign_initial_positions(node, x=0, level=0, seen=None):
            """Assign initial x positions to all nodes."""
            if seen is None:
                seen = set()

            if node in seen:
                return x

            seen.add(node)
            children = list(self.graph.neighbors(node))

            # For leaf nodes, just place them sequentially
            if not children:
                pos[node] = (x, -level)
                return x + width

            # Process children first
            start_x = x
            for child in children:
                if child not in seen:
                    x = _assign_initial_positions(child, x, level + 1, seen)

            # Center parent above its children
            if children:
                children_x = [pos[child][0] for child in children]
                pos[node] = (sum(children_x) / len(children), -level)
            else:
                pos[node] = (x, -level)

            return x

        def _adjust_subtrees(node, seen=None):
            """Adjust subtrees to maintain minimum distance."""
            if seen is None:
                seen = set()

            if node in seen:
                return

            seen.add(node)
            children = list(self.graph.neighbors(node))

            # Process all children first
            for child in children:
                _adjust_subtrees(child, seen)

            # If node has children, ensure they're properly spaced
            if len(children) > 1:
                # Sort children by x position
                children.sort(key=lambda n: pos[n][0])

                # Ensure minimum spacing between adjacent children
                for i in range(1, len(children)):
                    left_child = children[i - 1]
                    right_child = children[i]
                    min_spacing = width * (_get_tree_size(left_child, set()) +
                                           _get_tree_size(right_child, set())) / 2

                    actual_spacing = pos[right_child][0] - pos[left_child][0]

                    if actual_spacing < min_spacing:
                        # Move right subtree
                        delta = min_spacing - actual_spacing
                        for n, (x, y) in pos.items():
                            if x > pos[left_child][0]:
                                pos[n] = (x + delta, y)

                # Center parent above adjusted children positions
                children_x = [pos[child][0] for child in children]
                pos[node] = (sum(children_x) / len(children), pos[node][1])

        # Initialize positions dictionary
        pos = {}

        # First pass: assign initial positions
        _assign_initial_positions(root)

        # Second pass: adjust spacing
        _adjust_subtrees(root)

        # Normalize positions to center the tree
        min_x = min(x for x, y in pos.values())
        max_x = max(x for x, y in pos.values())

        # Scale positions to desired width
        scale = 2.0 / (max_x - min_x) if max_x > min_x else 1
        center_offset = (max_x + min_x) / 2

        # Return normalized and scaled positions
        return {node: ((x - center_offset) * scale, y * height)
                for node, (x, y) in pos.items()}

    def visualize(self, output_file: str = 'qep_tree.png'):
        """
        Visualize the query plan tree using NetworkX and save it to a file.
        Shows only node type, total cost (if not -1), and involved tables.

        Args:
            output_file: Path where the visualization should be saved
        """
        plt.figure(figsize=(15, 10))

        # Get root node (node with no incoming edges)
        root = [n for n, d in self.graph.in_degree() if d == 0][0]

        # Calculate positions with equidistant children
        pos = self._calculate_layout(root, width=1.0, height=1.0)

        # Draw nodes
        nx.draw_networkx_nodes(self.graph, pos,
                               node_size=3000,
                               node_color='lightblue',
                               node_shape='s')

        # Draw edges
        nx.draw_networkx_edges(self.graph, pos,
                               edge_color='gray',
                               arrows=True,
                               arrowsize=20)

        # Create simplified labels
        labels = {}
        for node, data in self.graph.nodes(data=True):
            label_parts = [f"{data['node_type']}"]

            # Only add cost if it's not -1
            if 'total_cost' in data and data['total_cost'] != -1:
                label_parts.append(f"Cost: {data['total_cost']:.2f}")

            # Add tables if present in the node's resolved_tables
            if 'resolved_tables' in data and data['resolved_tables']:
                label_parts.append(f"Tables: {', '.join(data['resolved_tables'])}")
            else:
                if 'original_tables' in data and data['original_tables']:
                    label_parts.append(f"Tables: {', '.join(data['original_tables'])}")

            labels[node] = '\n'.join(label_parts)

        # Add labels
        nx.draw_networkx_labels(self.graph, pos,
                                labels,
                                font_size=8,
                                verticalalignment='center')

        plt.title('Query Execution Plan Tree')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, bbox_inches='tight', dpi=300)
        plt.close()