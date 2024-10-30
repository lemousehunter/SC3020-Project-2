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

    def _collect_join_conditions(self) -> List[str]:
        """
        Collect all join conditions from the graph nodes.
        Returns a list of join condition strings with proper alias usage.
        """
        conditions = []
        for node, data in self.graph.nodes(data=True):
            if 'conditions' in data and data['conditions']:
                for condition in data['conditions']:
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
            'Index Only Scan': f'IndexOnlyScan({alias}',
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
            if 'Join' in data['node_type'] or data['node_type'] == 'Nested Loop':
                hint = self._get_join_hint(data)
                if hint:
                    hints.append(hint)

        return hints

    def _build_from_clause(self) -> str:
        """
        Build the FROM clause with proper table aliases and join conditions.
        """
        parts = []
        first_table = True
        seen_tables = set()

        # Start with leaf nodes (scan nodes)
        leaf_nodes = [n for n in self.graph.nodes() if len(list(self.graph.neighbors(n))) == 0]

        for node in leaf_nodes:
            data = self.graph.nodes[node]
            table = list(data['tables'])[0]
            if table not in seen_tables:
                alias = self.table_aliases[table]
                if first_table:
                    parts.append(f"{table} {alias}")
                    first_table = False
                else:
                    # Find join conditions involving this table's alias
                    join_conds = []
                    for cond in self.join_conditions:
                        if alias + "." in cond.lower():
                            join_conds.append(cond)

                    if join_conds:
                        join_clause = f"JOIN {table} {alias} ON {' AND '.join(join_conds)}"
                        parts.append(join_clause)
                seen_tables.add(table)

        return "\n".join(parts)

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

        # Build the query - with hints before SELECT
        if hint_clause:
            query = f"{hint_clause} SELECT {columns} FROM {self._build_from_clause()}"
        else:
            query = f"SELECT {columns} FROM {self._build_from_clause()}"

        return query


if __name__ == "__main__":
    # 1. Set up the database and get the original query plan
    db_manager = DatabaseManager('TPC-H')
    query = """
        select * from customer C, orders O where C.c_custkey = O.o_custkey;
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
        new_type=ScanType.INDEX_SCAN.value,
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