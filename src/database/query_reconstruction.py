from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Tuple
import networkx as nx
from collections import defaultdict

from src.database.databaseManager import DatabaseManager
from src.database.qep.qep_modifier import QueryModifier, JoinType, NodeType, QueryModification, ScanType
from src.database.qep.qep_parser import QEPParser
from src.database.qep.qep_visualizer import QEPVisualizer
from src.settings.filepaths import VIZ_DIR
from src.types.qep import JoinInfo


class QueryReconstructor:
    # TPC-H primary key mapping
    PRIMARY_KEYS = {
        'customer': 'c_custkey',
        'orders': 'o_orderkey',
        'lineitem': 'l_orderkey',
        'part': 'p_partkey',
        'supplier': 's_suppkey',
        'partsupp': ['ps_partkey', 'ps_suppkey'],
        'nation': 'n_nationkey',
        'region': 'r_regionkey'
    }

    # TPC-H join columns mapping
    JOIN_COLUMNS = {
        ('customer', 'orders'): ('c_custkey', 'o_custkey'),
        ('orders', 'lineitem'): ('o_orderkey', 'l_orderkey'),
        ('customer', 'nation'): ('c_nationkey', 'n_nationkey'),
        ('supplier', 'nation'): ('s_nationkey', 'n_nationkey'),
        ('part', 'partsupp'): ('p_partkey', 'ps_partkey'),
        ('supplier', 'partsupp'): ('s_suppkey', 'ps_suppkey'),
        ('nation', 'region'): ('n_regionkey', 'r_regionkey')
    }

    def __init__(self, graph: nx.DiGraph):
        """
        Initialize QueryReconstructor with a modified QEP graph.

        Args:
            graph: NetworkX DiGraph representing the modified query execution plan
        """
        self.graph = graph
        self.table_aliases = self._extract_table_aliases()
        self.table_filters = self._extract_table_filters()
        self.cte_counter = 0
        self.cte_table_mapping = {}  # Maps CTE names to their original tables

    def _extract_table_aliases(self) -> Dict[str, str]:
        """
        Extract table aliases from the graph.

        Returns:
            Dictionary mapping table names to their aliases
        """
        aliases = {}
        for _, data in self.graph.nodes(data=True):
            if 'relation_name' in data and 'alias' in data:
                table = data['relation_name']
                alias = data['alias']
                if alias != table:
                    aliases[table] = alias
        return aliases

    def _extract_table_filters(self) -> Dict[str, List[str]]:
        """
        Extract filters for each table from the graph.

        Returns:
            Dictionary mapping table names to their filter conditions
        """
        filters = defaultdict(list)
        for _, data in self.graph.nodes(data=True):
            if 'filter' in data and 'original_tables' in data:
                table_name = next(iter(data['original_tables']), None)
                if table_name:
                    filters[table_name].append(data['filter'])
        return filters

    def _get_table_key_columns(self, table_name: str, alias: str = None) -> List[str]:
        """
        Get the key columns for a table, with optional alias prefixing.

        Args:
            table_name: Name of the table
            alias: Optional alias to prefix columns with

        Returns:
            List of key column names (with aliases if specified)
        """
        key_cols = self.PRIMARY_KEYS.get(table_name, [])
        if not isinstance(key_cols, list):
            key_cols = [key_cols]

        if alias:
            return [f"{alias}.{col}" for col in key_cols]
        return key_cols

    def _extract_index_columns(self, node_data: Dict) -> List[str]:
        """
        Extract columns used in index scan from node data.

        Args:
            node_data: Node attributes dictionary

        Returns:
            List of column names used in index
        """
        index_cols = []
        table_name = next(iter(node_data['original_tables']))
        alias = node_data.get('alias', self.table_aliases.get(table_name, table_name))

        # First try to get columns from index condition
        if 'index_cond' in node_data:
            cond = node_data['index_cond']
            parts = cond.split('=')[0].strip()
            if '.' in parts:
                col = parts.split('.')[-1].strip('()')
                index_cols.append(f"{alias}.{col}")

        # Also check for any filter conditions that might benefit from an index
        if 'filter' in node_data:
            filter_cond = node_data['filter']
            if '=' in filter_cond:
                parts = filter_cond.split('=')[0].strip()
                if '.' in parts:
                    col = parts.split('.')[-1].strip('()')
                    if f"{alias}.{col}" not in index_cols:
                        index_cols.append(f"{alias}.{col}")

        # If no index conditions, use primary key
        if not index_cols:
            key_cols = self._get_table_key_columns(table_name, alias)
            index_cols.extend(key_cols)

        return index_cols

    def _build_bitmap_scan_cte(self, node_id: str) -> Tuple[str, str]:
        """
        Build a CTE that encourages PostgreSQL to use bitmap scans.
        Creates conditions favorable for bitmap index scans by using
        range conditions and IN clauses on indexed columns.

        Args:
            node_id: ID of the bitmap scan node

        Returns:
            Tuple of (SQL string for the CTE, CTE name)
        """
        node_data = self.graph.nodes[node_id]
        table_name = next(iter(node_data['original_tables']))
        alias = self.table_aliases.get(table_name, table_name)

        self.cte_counter += 1
        cte_name = f"bitmap_scan_{self.cte_counter}"
        self.cte_table_mapping[cte_name] = table_name

        # Get primary key and other indexed columns
        index_cols = self._extract_index_columns(node_data)
        if not index_cols:
            index_cols = self._get_table_key_columns(table_name, alias)

        # Create predicates that favor bitmap scans
        predicates = []

        # Extract any existing filter conditions
        existing_filters = self.table_filters.get(table_name, [])
        if existing_filters:
            predicates.extend(existing_filters)

        # For each indexed column, create range or IN conditions
        # that are likely to trigger bitmap scans
        for col in index_cols:
            col_name = col.split('.')[-1]  # Remove alias prefix

            # Create a subquery to get the range of values
            range_cte = f"""range_{self.cte_counter} AS (
                SELECT 
                    MIN({col}) as min_val,
                    MAX({col}) as max_val,
                    COUNT(DISTINCT {col}) as distinct_count
                FROM {table_name}
            )"""

            # Main CTE with bitmap-friendly predicates
            bitmap_predicates = f"""
                {col} >= (SELECT min_val FROM range_{self.cte_counter})
                AND {col} <= (SELECT max_val FROM range_{self.cte_counter})
                AND {col} IN (
                    SELECT DISTINCT {col}
                    FROM {table_name}
                    WHERE {col} >= (SELECT min_val FROM range_{self.cte_counter})
                      AND {col} <= (SELECT max_val FROM range_{self.cte_counter})
                )
            """
            predicates.append(bitmap_predicates)

        # Combine all predicates
        where_clause = " AND ".join(f"({pred})" for pred in predicates)

        # Build the final CTE that encourages bitmap scan
        query = f"""
            WITH {range_cte},
            {cte_name} AS (
                SELECT DISTINCT {alias}.*
                FROM {table_name} {alias}
                WHERE {where_clause}
            )"""

        return query.strip(), cte_name

    def _build_scan_cte(self, node_id: str) -> Tuple[str, str]:
        """
        Build a CTE for a scan operation.
        Enforces specific scan types through SQL patterns.

        Args:
            node_id: ID of the scan node

        Returns:
            Tuple of (SQL string for the CTE, CTE name)
        """
        node_data = self.graph.nodes[node_id]
        table_name = next(iter(node_data['original_tables']))
        alias = self.table_aliases.get(table_name, table_name)

        self.cte_counter += 1
        cte_name = f"scan_{self.cte_counter}"
        self.cte_table_mapping[cte_name] = table_name

        scan_type = node_data['node_type']

        print("scan_type:", scan_type)

        if scan_type == 'Index Scan':
            # For index scan, use ORDER BY to encourage index usage
            index_cols = self._extract_index_columns(node_data)
            order_by_clause = ', '.join(index_cols) if index_cols else f"{alias}.{self.PRIMARY_KEYS[table_name]}"

            query = f"""
                {cte_name} AS (
                    SELECT sub.*
                    FROM (
                        SELECT {alias}.*, 
                               ROW_NUMBER() OVER (
                                   ORDER BY {order_by_clause}
                               ) as rn
                        FROM {table_name} {alias}
                        {self._build_where_clause(table_name)}
                    ) sub
                )"""

        elif scan_type == 'Bitmap Heap Scan':
            # For bitmap heap scan, create simple range conditions
            index_col = self.PRIMARY_KEYS[table_name]

            query = f"""
                        {cte_name} AS (
                            WITH bounds AS (
                                SELECT 
                                    MIN({index_col}) as min_val,
                                    MAX({index_col}) as max_val,
                                    (MAX({index_col}) - MIN({index_col})) / 3 as range_size
                                FROM {table_name}
                            )
                            SELECT t.*
                            FROM {table_name} t, bounds b
                            WHERE (
                                t.{index_col} BETWEEN b.min_val AND (b.min_val + b.range_size)
                                OR t.{index_col} BETWEEN (b.min_val + b.range_size) AND (b.min_val + 2 * b.range_size)
                            )
                            {' AND ' + self._build_where_clause(table_name).replace('WHERE ', '')
            if self._build_where_clause(table_name) else ''}
                        )"""

        else:
            # Default to regular scan
            query = f"""
                {cte_name} AS (
                    SELECT {alias}.*
                    FROM {table_name} {alias}
                    {self._build_where_clause(table_name)}
                )"""

        return query.strip(), cte_name

    def _build_where_clause(self, table_name: str) -> str:
        """
        Build WHERE clause for a table using stored filters.

        Args:
            table_name: Name of the table

        Returns:
            WHERE clause SQL string
        """
        filters = self.table_filters.get(table_name, [])
        if not filters:
            return ""
        return f"WHERE {' AND '.join(filters)}"

    def _get_join_columns(self, table1: str, table2: str) -> Tuple[str, str]:
        """Get the joining columns for two tables."""
        # Try both orders of the tables
        if (table1, table2) in self.JOIN_COLUMNS:
            return self.JOIN_COLUMNS[(table1, table2)]
        if (table2, table1) in self.JOIN_COLUMNS:
            return tuple(reversed(self.JOIN_COLUMNS[(table2, table1)]))
        raise ValueError(f"No join columns defined for tables {table1} and {table2}")

    def _build_join_condition(self, left_cte: str, right_cte: str, left_tables: Set[str],
                              right_tables: Set[str]) -> str:
        """
        Build the join condition using proper table references and columns.

        Args:
            left_cte: Name of the left CTE
            right_cte: Name of the right CTE
            left_tables: Set of table names on the left side
            right_tables: Set of table names on the right side

        Returns:
            Join condition SQL string
        """
        if len(left_tables) != 1 or len(right_tables) != 1:
            raise ValueError("Exactly one table required on each side of the join")

        left_table = next(iter(left_tables))
        right_table = next(iter(right_tables))

        # Fix the reversed column names in the join condition
        if left_table == 'orders' and right_table == 'customer':
            return f"{left_cte}.o_custkey = {right_cte}.c_custkey"
        elif left_table == 'customer' and right_table == 'orders':
            return f"{left_cte}.c_custkey = {right_cte}.o_custkey"
        else:
            try:
                left_col, right_col = self._get_join_columns(left_table, right_table)
                return f"{left_cte}.{left_col} = {right_cte}.{right_col}"
            except ValueError:
                # Fallback to using primary keys
                left_key = self.PRIMARY_KEYS[left_table]
                right_key = self.PRIMARY_KEYS[right_table]
                if isinstance(left_key, list) or isinstance(right_key, list):
                    raise ValueError("Composite key joins not supported")
                return f"{left_cte}.{left_key} = {right_cte}.{right_key}"

    def _build_join_cte(self, node_id: str, left_cte: str, right_cte: str) -> Tuple[str, str]:
        """
        Build a CTE for a join operation.

        Args:
            node_id: ID of the join node
            left_cte: Name of the left CTE
            right_cte: Name of the right CTE

        Returns:
            Tuple of (SQL string for the CTE, CTE name)
        """
        join_info = self._get_join_info(node_id)
        if not join_info:
            raise ValueError(f"Node {node_id} is not a valid join node")

        self.cte_counter += 1
        cte_name = f"join_{self.cte_counter}"

        join_condition = self._build_join_condition(
            left_cte,
            right_cte,
            join_info.left_tables,
            join_info.right_tables
        )
        # Extract the columns used in the join condition
        left_join_col = join_condition.split('=')[0].split('.')[-1].strip()
        right_join_col = join_condition.split('=')[1].split('.')[-1].strip()

        # For merge joins, we need to ensure proper ordering
        if join_info.join_type == 'Merge Join':

            # Build the join condition using the ordered CTE names
            ordered_join_condition = f"ordered_left.{left_join_col} = ordered_right.{right_join_col}"

            query = f"""
                {cte_name} AS (
                    WITH ordered_left AS (
                        SELECT *
                        FROM {left_cte}
                        ORDER BY {left_join_col}
                    ),
                    ordered_right AS (
                        SELECT *
                        FROM {right_cte}
                        ORDER BY {right_join_col}
                    )
                    SELECT *
                    FROM ordered_left
                    INNER JOIN ordered_right
                    ON {ordered_join_condition}
                )"""
        elif join_info.join_type == 'Nested Loop':
            query = f"""
                {cte_name} AS (
                    SELECT l.*, r.*
                    FROM {left_cte} l,
                         LATERAL (
                             SELECT r.*
                             FROM {right_cte} r
                             WHERE r.{right_join_col} = l.{left_join_col}
                             LIMIT 1
                         ) r
                )"""
        else:
            join_keyword = 'INNER JOIN'  # Default to INNER JOIN for other types

            join_condition = self._build_join_condition(
                left_cte,
                right_cte,
                join_info.left_tables,
                join_info.right_tables
            )

            query = f"""
                {cte_name} AS (
                    SELECT *
                    FROM {left_cte}
                    {join_keyword} {right_cte}
                    ON {join_condition}
                )"""

        return query.strip(), cte_name

    def _reconstruct_subquery(self, node_id: str, ctes: List[str]) -> str:
        """
        Recursively reconstruct query from a node and its children.

        Args:
            node_id: ID of current node
            ctes: List to store CTEs

        Returns:
            Name of the CTE or subquery representing this node's result
        """
        node_data = self.graph.nodes[node_id]
        node_type = node_data.get('node_type', '')

        # Get child nodes
        children = list(self.graph.successors(node_id))

        # Handle scan nodes
        if 'Scan' in node_type:
            cte_sql, cte_name = self._build_scan_cte(node_id)
            ctes.append(cte_sql)
            return cte_name

        # Handle join nodes
        if 'Join' in node_type and len(children) == 2:
            left_cte = self._reconstruct_subquery(children[0], ctes)
            right_cte = self._reconstruct_subquery(children[1], ctes)
            cte_sql, cte_name = self._build_join_cte(node_id, left_cte, right_cte)
            ctes.append(cte_sql)
            return cte_name

        # For unexpected node types with children, just process children
        if children:
            # Process first child
            result_cte = self._reconstruct_subquery(children[0], ctes)

            # Process any additional children and join their results
            for child in children[1:]:
                child_cte = self._reconstruct_subquery(child, ctes)
                self.cte_counter += 1
                new_cte_name = f"result_{self.cte_counter}"

                # Create a simple join of the results
                cte_sql = f"""
                    {new_cte_name} AS (
                        SELECT *
                        FROM {result_cte}
                        CROSS JOIN {child_cte}
                    )"""
                ctes.append(cte_sql.strip())
                result_cte = new_cte_name

            return result_cte

        # For leaf nodes of unexpected types, return a placeholder
        self.cte_counter += 1
        cte_name = f"node_{self.cte_counter}"
        cte_sql = f"""
            {cte_name} AS (
                SELECT *
                FROM (VALUES (1)) AS placeholder(dummy)
            )"""
        ctes.append(cte_sql.strip())
        return cte_name

    def reconstruct_query(self) -> str:
        """
        Reconstruct the full SQL query from the modified QEP.

        Returns:
            Complete SQL query with CTEs
        """
        # Get root node (node with no incoming edges)
        roots = [n for n, d in self.graph.in_degree() if d == 0]
        if not roots:
            raise ValueError("Graph has no root node")

        ctes = []
        final_cte = self._reconstruct_subquery(roots[0], ctes)

        # Combine all CTEs with the final SELECT
        if ctes:
            cte_sql = ',\n'.join(ctes)
            query = f"""
            WITH {cte_sql}
            SELECT *
            FROM {final_cte}
            """
        else:
            # Handle case where no CTEs were created
            query = f"SELECT * FROM {final_cte}"

        return query.strip()

    def _get_join_info(self, node_id: str) -> Optional[JoinInfo]:
        """
        Extract join information from a join node.
        Modified to properly handle hash join tables.

        Args:
            node_id: ID of the node to analyze

        Returns:
            JoinInfo object if node is a join, None otherwise
        """
        node_data = self.graph.nodes[node_id]
        if 'node_type' not in node_data or not node_data['node_type'].endswith('Join'):
            return None

        # Get child nodes
        children = list(self.graph.successors(node_id))
        if len(children) != 2:
            return None

        left_tables = set()
        right_tables = set()

        # For Hash Join, look for Hash node and get tables from its child
        if node_data['node_type'] == 'Hash Join':
            for child in children:
                child_data = self.graph.nodes[child]
                if child_data.get('node_type') == 'Hash':
                    # Get tables from Hash node's child
                    hash_children = list(self.graph.successors(child))
                    if hash_children:
                        hash_child_data = self.graph.nodes[hash_children[0]]
                        right_tables = set(hash_child_data.get('original_tables', set()))
                else:
                    # Non-hash child is the left side
                    left_tables = set(child_data.get('original_tables', set()))
        else:
            # For other join types, get tables directly from children
            left_data = self.graph.nodes[children[0]]
            right_data = self.graph.nodes[children[1]]
            left_tables = set(left_data.get('original_tables', set()))
            right_tables = set(right_data.get('original_tables', set()))

        # If tables not found in original_tables, try other attributes
        if not left_tables and 'left_tables' in node_data:
            left_tables = set(node_data['left_tables'])
        if not right_tables and 'right_tables' in node_data:
            right_tables = set(node_data['right_tables'])

        # Extract join condition
        join_cond = None
        if 'hash_cond' in node_data:
            join_cond = node_data['hash_cond']
        elif 'merge_cond' in node_data:
            join_cond = node_data['merge_cond']
        elif 'join_filter' in node_data:
            join_cond = node_data['join_filter']

        return JoinInfo(
            left_tables=left_tables,
            right_tables=right_tables,
            condition=join_cond,
            join_type=node_data['node_type']
        )


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

    # 3. Create modifications
    # Change the sequential scan on customer table to a bitmap index scan
    scan_modification = QueryModification(
        node_type=NodeType.SCAN,
        original_type=ScanType.SEQ_SCAN.value,
        new_type=ScanType.BITMAP_INDEX_SCAN.value,
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
    reconstructor = QueryReconstructor(modified_graph)
    modified_query = reconstructor.reconstruct_query()

    # 6. Print the modified query
    print(modified_query)

    # 7. Visualize the modified graph
    db_manager = DatabaseManager('TPC-H')
    res = db_manager.get_qep(modified_query)
    q = QEPParser()
    tree = q.parse(res)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    QEPVisualizer(tree).visualize(VIZ_DIR / "modified_explained_qep_tree.png")


    # 5. Visualize the modified graph
    #visualizer = QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_qep_tree.png")