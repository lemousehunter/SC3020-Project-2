import re
from typing import Optional, List

import networkx as nx

from src.database.qep.qep_change_checker import QEPChangeChecker


class QueryModifier:
    def __init__(self, query: str, hint: str):
        self.query = query
        self.hint = hint

    def modify(self):
        return self.hint + "\n" + self.query


if __name__ == "__main__":
    from src.database.qep.qep_modifier import QEPModifier, JoinType, NodeType, TypeModification, ScanType
    from src.database.qep.qep_parser import QEPParser
    from src.database.qep.qep_visualizer import QEPVisualizer
    from src.settings.filepaths import VIZ_DIR
    from src.database.databaseManager import DatabaseManager
    from src.custom_types.qep_types import NodeType, ScanType, JoinType, InterJoinOrderModificationSpecced
    from src.database.hint_generator import HintConstructor

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

    qep_data: List = db_manager.get_qep(query)

    # 2. Parse the original plan
    parser = QEPParser()
    original_graph, ordered_join_pairs, alias_map, join_node_id_map = parser.parse(qep_data, None)
    QEPVisualizer(original_graph).visualize(VIZ_DIR / "original_qep.png")

    # 3. Create modifications
    # Change the sequential scan on customer table to an index scan
    scan_modification = TypeModification(
        node_type=NodeType.SCAN,
        original_type=ScanType.SEQ_SCAN.value,
        new_type=ScanType.BITMAP_HEAP_SCAN.value,
        tables={'c'},
        node_id="SOMESTRING"
    )

    # Change the nested loop join to a hash join
    join_modification = TypeModification(
        node_type=NodeType.JOIN,
        original_type=JoinType.HASH_JOIN.value,
        new_type=JoinType.NESTED_LOOP.value,
        tables={'c', 'o', "l", "s"},
        node_id="SOMESTRING"
    )

    join_order_modification_1 = InterJoinOrderModificationSpecced(
        join_order_1=('o', 'c'),
        join_type_1=JoinType.NESTED_LOOP.value,
        join_order_2=('l', 's'),
        join_type_2=JoinType.HASH_JOIN.value
    )

    # 4. Apply modifications
    modifier = QEPModifier(original_graph, ordered_join_pairs, alias_map)
    modifier.add_modification(scan_modification)
    modifier.add_modification(join_modification)
    modifier.add_modification(join_order_modification_1)
    #modifier.add_modification(join_order_modification_2)

    example_modification_request = {
        'modifications': [
            {
                'node_type': 'SCAN',
                'original_type': 'Seq Scan',
                'new_type': 'Bitmap Heap Scan',
                'tables': ['customer'],
                'node_id': 1
            },
            {
                'node_type': 'JOIN',
                'original_type': 'Hash Join',
                'new_type': 'Nested Loop',
                'tables': ['customer', 'orders', 'lineitem', 'supplier'],
                'node_id': 2
            }
        ]
    }

    modified_graph, modifications = modifier.apply_modifications(False)
    QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_pre-explained_qep_tree.png")

    # 5 Generate Hint
    hint, hint_lst, hint_expl = HintConstructor(modified_graph).generate_hints()
    print(hint)
    print("Hint Explanations\n{}".format(hint_expl))

    # 6 Modify Query (pre-pend hint)
    modified_query = QueryModifier(
        query=query,
        hint=hint
    ).modify()
    print(modified_query)

    # 7. Visualize the modified graph
    res = db_manager.get_qep(modified_query)
    q = QEPParser()
    tree, new_ordered_join_pairs, new_alias_map, new_join_node_id_map = q.parse(res, join_node_id_map)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    QEPVisualizer(tree).visualize(VIZ_DIR / "modified_explained_qep_tree.png")

    # 8. Change Checker
    # Check if the query has been modified correctly
    QEPChangeChecker().check(tree, modified_graph, modifications, False)