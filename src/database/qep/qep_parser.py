import networkx as nx
from typing import Dict, Any, Optional, List, Tuple, Set
import uuid
from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_visualizer import QEPVisualizer
from src.settings.filepaths import VIZ_DIR


class QEPParser:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.alias_map = {}  # Map aliases to original table names

    def reset(self):
        """Reset the parser state."""
        self.graph = nx.DiGraph()
        self.alias_map.clear()

    def _register_alias(self, alias: str, table_name: str):
        """Register a table alias."""
        self.alias_map[alias.lower()] = table_name

    def _resolve_table_name(self, identifier: str) -> str:
        """
        Resolve a table identifier to its full original name.
        Returns the original identifier if no mapping exists.
        """
        return self.alias_map.get(identifier.lower(), identifier)

    def _collect_descendant_tables(self, node_id: str, visited: Set[str] = None) -> Set[str]:
        """
        Recursively collect all tables from a node's descendants.

        Args:
            node_id: ID of the current node
            visited: Set of already visited nodes to prevent cycles

        Returns:
            Set of table names from all descendants
        """
        if visited is None:
            visited = set()

        if node_id in visited:
            return set()

        visited.add(node_id)
        tables = set(self.graph.nodes[node_id].get('tables', []))

        # Recursively collect tables from all descendants
        for child in self.graph.neighbors(node_id):
            tables.update(self._collect_descendant_tables(child, visited))

        return tables

    def _process_join_condition(self, condition: str) -> Tuple[set, List[str]]:
        """
        Process a join condition to extract and resolve table names and conditions.
        Returns: (set of table names, list of resolved conditions)
        eg.: "(c.c_custkey = o.o_custkey)" -> ({"customer", "orders"}, ["customer.c_custkey = orders.o_custkey"])
        """
        tables = set()
        resolved_conditions = []
        if not condition:
            return tables, resolved_conditions

        # Split on logical operators (AND, OR) if present
        conditions = condition.split(' AND ')
        for cond in conditions:
            resolved_condition = cond
            # Split on comparison operators and other delimiters
            parts = cond.replace('(', ' ').replace(')', ' ').replace('=', ' ').split()

            for part in parts:
                if '.' in part:
                    table_alias, column = part.split('.')
                    resolved_table = self._resolve_table_name(table_alias)
                    if resolved_table != table_alias:  # Only add if we successfully resolved an alias
                        tables.add(resolved_table)
                        # Replace alias with resolved table name in condition
                        resolved_condition = resolved_condition.replace(
                            f"{table_alias}.", f"{resolved_table}."
                        )

            if resolved_condition.strip():
                resolved_conditions.append(resolved_condition.strip())

        return tables, resolved_conditions

    def _extract_join_info(self, node_data: Dict[str, Any]) -> tuple[set[set], list[str]]:
        """Extract join tables and conditions from a node."""
        all_tables = set()
        all_conditions = []

        # Process various types of join conditions
        condition_keys = [
            'Hash Cond',
            'Join Filter',
            'Filter',
            'Index Cond',
            'Merge Cond',
            'Recheck Cond'
        ]

        for key in condition_keys:
            if key in node_data:
                tables, conditions = self._process_join_condition(node_data[key])
                all_tables.update(tables)
                all_conditions.extend(conditions)

        return all_tables, all_conditions

    def _extract_tables(self, node_data: Dict[str, Any]) -> Tuple[Set[str], List[str]]:
        """Extract and resolve all table names and conditions from a node."""
        tables = set()
        conditions = []

        # Handle direct table references
        if 'Relation Name' in node_data:
            table_name = node_data['Relation Name']
            alias = node_data.get('Alias', table_name)
            self._register_alias(alias, table_name)
            tables.add(table_name)

        # Process join conditions
        join_tables, join_conditions = self._extract_join_info(node_data)
        tables.update(join_tables)
        conditions.extend(join_conditions)

        return tables, conditions

    def _parse_node(self, node_data: Dict[str, Any], parent_id: Optional[str] = None, is_root: bool = False) -> str:
        """Parse a single node and its children."""
        node_id = str(uuid.uuid4())
        tables = set()
        conditions = []

        # Process children first to ensure all aliases are registered
        child_nodes = []
        if 'Plans' in node_data:
            for child_plan in node_data['Plans']:
                child_id = self._parse_node(child_plan, node_id, is_root=False)
                child_nodes.append(child_id)

        # Extract tables and conditions based on node type
        node_type = node_data.get('Node Type', '')

        if 'Join' in node_type or node_type == 'Nested Loop':
            # First get the immediate tables and conditions from this node
            node_tables, node_conditions = self._extract_join_info(node_data)
            tables.update(node_tables)
            conditions.extend(node_conditions)

            # Then collect all tables from descendants for join nodes
            for child_id in child_nodes:
                descendant_tables = self._collect_descendant_tables(child_id)
                tables.update(descendant_tables)
        else:
            # For non-join nodes, extract tables and conditions normally
            node_tables, node_conditions = self._extract_tables(node_data)
            tables.update(node_tables)
            conditions.extend(node_conditions)

        node_attrs = {
            'node_type': node_type,
            'tables': sorted(tables),  # Sort for consistent ordering
            'cost': node_data.get('Total Cost', 0.0),
            'is_root': is_root,
            'conditions': conditions
        }

        # Add node to graph
        self.graph.add_node(node_id, **node_attrs)

        # Connect to parent if exists
        if parent_id is not None:
            self.graph.add_edge(parent_id, node_id)

        return node_id

    def parse(self, qep_data: List) -> nx.DiGraph:
        """Parse the QEP data into a graph."""
        self.reset()

        if isinstance(qep_data, list) and len(qep_data) > 0:
            if isinstance(qep_data[0], tuple) and len(qep_data[0]) > 0:
                if isinstance(qep_data[0][0], list) and len(qep_data[0][0]) > 0:
                    root_plan = qep_data[0][0][0].get('Plan', {})
                    self._parse_node(root_plan, parent_id=None, is_root=True)

        return self.graph

    def print_nodes(self):
        """Print all nodes and their attributes in a hierarchical format."""
        def get_node_level(node):
            root = [n for n, d in self.graph.nodes(data=True) if d.get('is_root', False)][0]
            try:
                return nx.shortest_path_length(self.graph, root, node)
            except:
                return 0

        nodes = list(self.graph.nodes(data=True))
        nodes.sort(key=lambda x: get_node_level(x[0]))

        print("\nQuery Execution Plan Node Details:")
        print("=" * 50)

        for node_id, attrs in nodes:
            level = get_node_level(node_id)
            indent = "  " * level

            print(f"\n{indent}Node Level {level}:")
            print(f"{indent}{'─' * 20}")
            print(f"{indent}Type: {attrs['node_type']}")
            print(f"{indent}Cost: {attrs['cost']:.2f}")
            print(f"{indent}Tables: {', '.join(attrs['tables']) if attrs['tables'] else 'None'}")
            print(f"{indent}Is Root: {attrs['is_root']}")
            if attrs['conditions']:
                print(f"{indent}Conditions: {', '.join(attrs['conditions'])}")



if __name__ == "__main__":
    db_manager = DatabaseManager('TPC-H')
    #res = db_manager.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
    #res = db_manager.get_qep("select * from customer C, orders O where C.c_custkey = O.o_custkey")
    #query = """
    #    select * from customer C, orders O where C.c_custkey = O.o_custkey;
    #    """
    query = """
    select 
    /*+ Leading( ( ( (l s) o) c) )  NestLoop( c o l s) HashJoin( l s ) HashJoin( l o ) BitmapScan(c) */
    * 
from customer C, orders O, lineitem L, supplier S
where C.c_custkey = O.o_custkey 
  and O.o_orderkey = L.l_orderkey
  and L.l_suppkey = S.s_suppkey
  and L.l_quantity > (
    select avg(L2.l_quantity) 
    from lineitem L2 
    where L2.l_suppkey = S.s_suppkey
  )
    """
    #query = """
    #select
    #/*+ Leading( ( ( (l s) o) c) )  NestLoop( c o l s) HashJoin( l s ) HashJoin( l o ) BitmapScan(c) */
    #* from customer c
    #join orders o on (c.c_custkey = o.o_custkey)
    #join lineitem l on (o.o_orderkey = l.l_orderkey)
    #join supplier s on (l.l_suppkey = s.s_suppkey);"""
    res = db_manager.get_qep(query)

    q = QEPParser()
    tree = q.parse(res)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    QEPVisualizer(tree).visualize(VIZ_DIR / "qep_tree.png")
    q.print_nodes()
    #q.visualize(VIZ_DIR / "qep_tree.png")