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
        self._print_join_order()

    def _print_join_order(self):
        print("============== JOIN ORDER ==============")
        for join in self.join_order:
            print(join['type'], join['tables'], join['conditions'])
        print("========================================")

    def _collect_table_aliases(self) -> Dict[str, str]:
        """
        Collect table aliases from the graph nodes.
        Returns a dict mapping table names to their lowercase aliases.
        """
        aliases = {}
        # Look for leaf nodes (no outgoing edges) which are typically scan nodes
        for node, data in self.graph.nodes(data=True):
            if len(list(self.graph.neighbors(node))) == 0:  # Leaf node
                if data['tables'] and len(data['tables']) == 1:
                    table = data['tables'][0]
                    # Create lowercase alias as first letter of table name
                    alias = table[0].lower()
                    aliases[table] = alias
        return aliases

    def _get_leading_hint(self) -> str:
        """
        Generate Leading() hint based on the determined join order.
        Returns a string like 'Leading(table1 table2 (table3 table4))'
        """
        if not self.join_order:
            return ""

        # Extract tables in join order
        tables_in_order = []
        processed_tables = set()

        # Start with the first join's tables
        first_join = self.join_order[0]
        first_tables = list(first_join['tables'])
        # Convert to aliases and add to the list
        tables_in_order.extend(self.table_aliases[t] for t in first_tables)
        processed_tables.update(first_tables)

        # Process remaining joins
        for join in self.join_order[1:]:
            new_tables = join['tables'] - processed_tables
            if new_tables:
                # Convert to aliases and add to the list
                tables_in_order.extend(self.table_aliases[t] for t in new_tables)
                processed_tables.update(new_tables)

        # Construct the Leading hint
        if tables_in_order:
            return f"Leading({' '.join(tables_in_order)})"
        return ""

    def _is_valid_condition(self, condition: str) -> bool:
        """
        Check if a condition is valid for inclusion in the SQL query.
        Filters out internal execution plan constructs and handles subqueries.
        """
        invalid_patterns = [
            'SubPlan',
            'InitPlan',
            '(SubPlan',
            '(InitPlan',
        ]
        if any(pattern in condition for pattern in invalid_patterns):
            return False

        # Additional validation for subquery conditions
        if '(' in condition and ')' in condition:
            depth = 0
            for char in condition:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                if depth < 0:  # Unmatched parentheses
                    return False
            return depth == 0
        return True

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
                        if aliased_condition not in conditions:
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

        print("getting hint for node:", node_type)

        return join_hint_map.get(node_type, '')

    def _collect_hints(self) -> List[str]:
        """
        Collect all hints from the graph nodes, including the Leading hint.
        """
        hints = []

        # Add Leading hint first to enforce join order
        leading_hint = self._get_leading_hint()
        if leading_hint:
            hints.append(leading_hint)

        # Process scan nodes
        for node, data in self.graph.nodes(data=True):
            if len(data['tables']) == 1:  # Scan node
                hint = self._get_scan_hint(data)
                if hint:
                    hints.append(hint)

        # Process join nodes
        for node, data in self.graph.nodes(data=True):
            if 'Join' in data['node_type'] or data['node_type'] == "Nested Loop":
                hint = self._get_join_hint(data)
                if hint:
                    hints.append(hint)

        return hints

    def _determine_join_order(self) -> List[Dict]:
        """
        Determine the join order by traversing from root to leaves.
        Joins closer to the root should be processed first.
        """
        joins = []
        visited = set()

        # Find root node
        root = [n for n, d in self.graph.nodes(data=True) if d.get('is_root', False)][0]

        def traverse_top_down(node_id: str, level: int = 0):
            """
            Traverse the tree from top to bottom, recording joins in order.
            """
            if node_id in visited:
                return
            visited.add(node_id)

            node_data = self.graph.nodes[node_id]
            node_type = node_data.get('node_type', '')

            # Process current node if it's a join
            if 'Join' in node_type or node_type == 'Nested Loop':
                valid_conditions = [
                    cond for cond in node_data.get('conditions', [])
                    if self._is_valid_condition(cond)
                ]

                joins.append({
                    'node_id': node_id,
                    'type': node_type,
                    'tables': set(node_data.get('tables', [])),
                    'conditions': valid_conditions,
                    'level': level  # Add level for sorting
                })

            # Process children
            for child in self.graph.neighbors(node_id):
                traverse_top_down(child, level + 1)

        # Start traversal from root
        traverse_top_down(root)

        # Sort joins by level (ascending) to ensure top-down order
        joins.sort(key=lambda x: x['level'])

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
        Build the FROM clause following the join order strictly from the join nodes.
        Uses table pairs defined in each join node.
        """
        if not self.join_order:
            return ""

        processed_tables = set()
        join_clauses = []
        non_join_conditions = []

        def get_join_conditions(node_id: str, tables: Set[str]) -> List[str]:
            """Get join conditions for specific tables from a node."""
            conditions = []
            node_data = self.graph.nodes[node_id]

            for condition in node_data.get('conditions', []):
                if self._is_valid_condition(condition):
                    # Replace table names with aliases in the condition
                    aliased_condition = condition
                    for table, alias in self.table_aliases.items():
                        aliased_condition = aliased_condition.replace(f"{table}.", f"{alias}.")

                    # Check if this is a join condition (contains =)
                    if '=' in aliased_condition:
                        tables_in_cond = set(self._extract_tables_from_condition(condition))
                        # Only include if condition involves the tables we're joining
                        if tables_in_cond.issubset(tables):
                            conditions.append(aliased_condition)
                    else:
                        # Store non-join conditions for the WHERE clause
                        if aliased_condition not in non_join_conditions:
                            non_join_conditions.append(aliased_condition)

            return conditions

        # Start with the first join
        first_join = self.join_order[0]
        tables_to_join = first_join['tables']
        first_table = next(iter(tables_to_join))
        first_alias = self.table_aliases[first_table]
        base_query = f"{first_table} {first_alias}"
        processed_tables.add(first_table)

        # Add remaining tables from first join
        remaining_tables = tables_to_join - {first_table}
        if remaining_tables:
            table = next(iter(remaining_tables))
            alias = self.table_aliases[table]
            conditions = get_join_conditions(first_join['node_id'], tables_to_join)
            if conditions:
                join_clauses.append(f"JOIN {table} {alias} ON {' AND '.join(conditions)}")
            else:
                join_clauses.append(f"CROSS JOIN {table} {alias}")
            processed_tables.add(table)

        # Process remaining joins in order
        for join in self.join_order[1:]:
            join_tables = join['tables']
            # Get tables not yet processed
            new_tables = join_tables - processed_tables
            if not new_tables:
                continue

            # Add each new table with appropriate conditions
            for table in new_tables:
                alias = self.table_aliases[table]
                # Get conditions involving this table and any processed tables
                relevant_tables = {table} | (join_tables & processed_tables)
                conditions = get_join_conditions(join['node_id'], relevant_tables)

                if conditions:
                    join_clauses.append(f"JOIN {table} {alias} ON {' AND '.join(conditions)}")
                else:
                    join_clauses.append(f"CROSS JOIN {table} {alias}")
                processed_tables.add(table)

        # Build the complete query
        query_parts = [base_query]
        if join_clauses:
            query_parts.extend(join_clauses)

        query = "\n".join(query_parts)

        # Add WHERE clause for non-join conditions
        if non_join_conditions:
            query += f"\nWHERE {' AND '.join(non_join_conditions)}"

        return query

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
        join_tree = self._build_join_tree()
        query = f"{hint_clause} SELECT {columns} FROM {join_tree}"

        return query.strip()

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
        join_tree = self._build_join_tree()
        query = f"{hint_clause} SELECT {columns} FROM {join_tree}"

        return query.strip()



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
    modifier.add_modification(scan_modification)
    modifier.add_modification(join_modification)

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