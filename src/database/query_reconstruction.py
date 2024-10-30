import json
from collections import defaultdict
from enum import Enum, auto
from src.database.qep.qep_modifier import QueryModifier, JoinType, NodeType, QueryModification, ScanType
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_visualizer import QEPVisualizer
from src.settings.filepaths import VIZ_DIR
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Tuple, Any
import networkx as nx
from src.database.databaseManager import DatabaseManager
from src.types.qep_types import JoinInfo, NodeType, ScanType, JoinType

import networkx as nx

from typing import List, Dict, Optional, Any

from typing import Dict, Set, List, Tuple
import networkx as nx
from collections import defaultdict


class QueryConstructor:
    def __init__(self, modified_graph: nx.DiGraph):
        """
        Initialize QueryConstructor with a modified query execution plan graph.

        Args:
            modified_graph: NetworkX DiGraph representing the modified query plan
        """
        self.graph = modified_graph
        self.table_aliases = self._collect_table_aliases()
        self.join_conditions = self._collect_join_conditions()
        self.join_order = self._determine_join_order()
        print(self.join_order)

    def _collect_table_aliases(self) -> Dict[str, str]:
        """
        Collect table aliases from the graph nodes.
        Returns a dict mapping table names to their aliases.
        """
        aliases = {}
        # Look for leaf nodes (no outgoing edges) which are typically scan nodes
        for node, data in self.graph.nodes(data=True):
            if len(list(self.graph.neighbors(node))) == 0:  # Leaf node
                if data['tables'] and len(data['tables']) == 1:
                    table = list(data['tables'])[0]
                    # Create default alias as first letter of table name
                    alias = table[0].lower()
                    aliases[table] = alias
        return aliases

    def _is_valid_condition(self, condition: str) -> bool:
        """
        Check if a condition is valid for inclusion in the SQL query.
        Filters out internal execution plan constructs.
        """
        invalid_patterns = [
            'SubPlan',
            'InitPlan',
            '(SubPlan',
            '(InitPlan',
        ]
        return not any(pattern in condition for pattern in invalid_patterns)

    def _collect_join_conditions(self) -> List[str]:
        """
        Collect all join conditions from the graph nodes.
        Returns a list of join condition strings with proper alias usage.
        """
        conditions = []
        for node, data in self.graph.nodes(data=True):
            if 'conditions' in data and data['conditions']:
                for condition in data['conditions']:
                    # Only include valid conditions
                    if self._is_valid_condition(condition):
                        # Replace full table names with aliases in conditions
                        aliased_condition = condition
                        for table, alias in self.table_aliases.items():
                            aliased_condition = aliased_condition.replace(
                                f"{table}.", f"{alias}."
                            )
                        conditions.append(aliased_condition)
        return conditions

    def _get_scan_hint(self, node_data: Dict) -> str:
        """
        Generate scan hint based on node type using table alias.
        """
        node_type = node_data['node_type']
        table = list(node_data['tables'])[0]  # Scan nodes have exactly one table
        alias = self.table_aliases[table]

        scan_hint_map = {
            'Seq Scan': f'SeqScan({alias})',
            'Index Scan': f'IndexScan({alias})',
            'Index Only Scan': f'IndexOnlyScan({alias})',
            'Bitmap Heap Scan': f'BitmapScan({alias})',
            'Tid Scan': f'TidScan({alias})'
        }

        return scan_hint_map.get(node_type, '')

    def _get_join_hint(self, node_data: Dict) -> str:
        """
        Generate join hint based on node type using table aliases.
        """
        node_type = node_data['node_type']
        tables = sorted(node_data['tables'])  # Sort for consistent ordering
        # Convert tables to aliases
        aliases = [self.table_aliases[table] for table in tables]

        join_hint_map = {
            'Nested Loop': f'NestLoop({" ".join(aliases)})',
            'Hash Join': f'HashJoin({" ".join(aliases)})',
            'Merge Join': f'MergeJoin({" ".join(aliases)})'
        }

        return join_hint_map.get(node_type, '')

    def _collect_hints(self) -> List[str]:
        """
        Collect all hints from the graph nodes.
        """
        hints = []

        # Process scan nodes first
        for node, data in self.graph.nodes(data=True):
            if len(data['tables']) == 1:  # Scan node
                hint = self._get_scan_hint(data)
                if hint:
                    hints.append(hint)

        # Then process join nodes
        for node, data in self.graph.nodes(data=True):
            if 'Join' in data['node_type']:
                hint = self._get_join_hint(data)
                if hint:
                    hints.append(hint)

        return hints

    def _determine_join_order(self) -> List[Dict]:
        """
        Determine the join order by traversing the QEP tree from top down,
        starting from the root join node or the join node closest to root.
        Returns a list of join operations in execution order.
        """
        joins = []
        visited = set()

        def get_root_or_nearest_join():
            """Find the root node or the nearest join node to root."""
            root = [n for n, d in self.graph.nodes(data=True) if d.get('is_root', False)][0]
            node = root
            node_data = self.graph.nodes[node]

            # If root is not a join, traverse down until we find the first join
            if 'Join' not in node_data['node_type']:
                queue = list(self.graph.neighbors(node))
                while queue:
                    curr_node = queue.pop(0)
                    curr_data = self.graph.nodes[curr_node]
                    if 'Join' in curr_data['node_type']:
                        return curr_node
                    queue.extend(list(self.graph.neighbors(curr_node)))
            return node

        def traverse_joins(node_id):
            """Traverse the join nodes from top to bottom."""
            if node_id in visited:
                return
            visited.add(node_id)

            node_data = self.graph.nodes[node_id]
            node_type = node_data.get('node_type', '')

            # Record join information first (top-down approach)
            if 'Join' in node_type:
                # Filter conditions
                valid_conditions = [
                    cond for cond in node_data.get('conditions', [])
                    if self._is_valid_condition(cond)
                ]

                joins.append({
                    'node_id': node_id,
                    'type': node_type,
                    'tables': set(node_data.get('tables', [])),
                    'conditions': valid_conditions
                })

            # Then process child nodes
            children = list(self.graph.neighbors(node_id))
            for child in children:
                child_data = self.graph.nodes[child]
                # Ensure we process join nodes before other types
                if 'Join' in child_data.get('node_type', ''):
                    traverse_joins(child)

            # Process non-join children last
            for child in children:
                child_data = self.graph.nodes[child]
                if 'Join' not in child_data.get('node_type', ''):
                    traverse_joins(child)

        # Start traversal from root join or nearest join to root
        start_node = get_root_or_nearest_join()
        traverse_joins(start_node)
        return joins

    def _clean_table_name(self, table_name: str) -> str:
        """
        Clean table name by removing parentheses and other special characters.
        """
        # Remove common special characters
        cleaned = table_name.strip('() \t\n\r')
        return cleaned

    def _extract_tables_from_condition(self, condition: str) -> List[str]:
        """
        Extract tables in the order they appear in a join condition.
        Handles special characters and parentheses.
        Example: "customer.c_custkey = orders.o_custkey" -> ["customer", "orders"]
        """
        tables = []
        # Remove any parentheses around the entire condition
        condition = condition.strip('()')
        parts = condition.split('=')

        for part in parts:
            # Split on spaces and look for table references
            terms = part.strip().split()
            for term in terms:
                if '.' in term:
                    table = self._clean_table_name(term.split('.')[0])
                    # Convert alias back to table name if needed
                    for full_name, alias in self.table_aliases.items():
                        if table == alias:
                            table = full_name
                            break
                    if table and table not in tables:
                        tables.append(table)
        return tables

    def _build_join_tree(self) -> str:
        """
        Build the FROM clause following the join condition order.
        """
        processed_tables = set()
        join_clauses = []
        table_order = []

        # Process each join in order
        for join in self.join_order:
            for condition in join.get('conditions', []):
                if not self._is_valid_condition(condition):
                    continue

                # Extract tables in order from the condition
                tables_in_condition = self._extract_tables_from_condition(condition)

                # Add tables to the order if not already processed
                for table in tables_in_condition:
                    if table not in table_order:
                        table_order.append(table)

                # First table in the condition that hasn't been processed becomes the next table to join
                tables_to_join = [t for t in tables_in_condition if t not in processed_tables]

                if not tables_to_join:
                    continue

                # First table becomes base table if we haven't started yet
                if not processed_tables:
                    first_table = tables_to_join[0]
                    first_alias = self.table_aliases[first_table]
                    base_query = f"{first_table} {first_alias}"
                    processed_tables.add(first_table)
                    tables_to_join = tables_to_join[1:]

                # Create join clauses for remaining tables
                for table in tables_to_join:
                    alias = self.table_aliases[table]
                    # Find all conditions involving this table and already processed tables
                    relevant_conditions = []
                    for join_cond in join.get('conditions', []):
                        if self._is_valid_condition(join_cond):
                            # Replace table names with aliases in conditions
                            aliased_condition = join_cond
                            for t, a in self.table_aliases.items():
                                aliased_condition = aliased_condition.replace(f"{t}.", f"{a}.")

                            # Check if condition involves current table and any processed table
                            tables_in_cond = self._extract_tables_from_condition(join_cond)
                            if table in tables_in_cond and any(t in processed_tables for t in tables_in_cond):
                                relevant_conditions.append(aliased_condition)

                    join_clause = f"JOIN {table} {alias}"
                    if relevant_conditions:
                        join_clause += f" ON {' AND '.join(relevant_conditions)}"
                    join_clauses.append(join_clause)
                    processed_tables.add(table)

        # Handle case where no join conditions exist
        if not processed_tables:
            first_table = next(iter(self.table_aliases.keys()))
            base_query = f"{first_table} {self.table_aliases[first_table]}"

        return f"{base_query}\n{' '.join(join_clauses)}"

    def construct_query(self) -> str:
        """
        Construct the complete SQL query with hints.
        """
        # Sort aliases for consistent output
        sorted_aliases = sorted(self.table_aliases.items(), key=lambda x: x[1])

        # Collect all hints
        hints = self._collect_hints()
        hint_clause = f"/*+ {' '.join(hints)} */" if hints else ""

        # Build column selection with aliases
        columns = ", ".join(f"{alias}.*" for _, alias in sorted_aliases)

        # Build the query
        query = f"{hint_clause} SELECT {columns} FROM {self._build_join_tree()}"

        return query



if __name__ == "__main__":
    # 1. Set up the database and get the original query plan
    db_manager = DatabaseManager('TPC-H')
    query = """
        select * 
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

    qep_data = db_manager.get_qep(query)

    # 2. Parse the original plan
    parser = QEPParser()
    original_graph = parser.parse(qep_data)
    QEPVisualizer(original_graph).visualize(VIZ_DIR / "original_qep.png")

    # 3. Create modifications
    # Change the sequential scan on customer table to a bitmap index scan
    scan_modification = QueryModification(
        node_type=NodeType.SCAN,
        original_type=ScanType.SEQ_SCAN.value,
        new_type=ScanType.BITMAP_HEAP_SCAN.value,
        tables={'customer'}
    )

    # Change the nested loop join to a hash join
    join_modification = QueryModification(
        node_type=NodeType.JOIN,
        original_type=JoinType.HASH_JOIN.value,
        new_type=JoinType.NESTED_LOOP.value,
        tables={'customer', 'orders'}
    )

    # 4. Apply modifications
    modifier = QueryModifier(original_graph)
    #modifier.add_modification(scan_modification)
    #modifier.add_modification(join_modification)

    modified_graph = modifier.apply_modifications()
    QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_pre-explained_qep_tree.png")

    # 5. Reconstruct Query
    constructor = QueryConstructor(modified_graph)
    modified_query = constructor.construct_query()


    # 6. Print the modified query
    print(modified_query)

    # 7. Visualize the modified graph
    db_manager = DatabaseManager('TPC-H')
    res = db_manager.get_qep(modified_query)
    print(res)
    q = QEPParser()
    tree = q.parse(res)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    QEPVisualizer(tree).visualize(VIZ_DIR / "modified_explained_qep_tree.png")