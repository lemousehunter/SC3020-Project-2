import re
from typing import Optional, List

import networkx as nx


class QueryModifier:
    def __init__(self, query: str, hint: str):
        self.query = query
        self.hint = hint

    def modify(self):
        return self.hint + "\n" + self.query


if __name__ == "__main__":
    from src.database.qep.qep_modifier import QEPModifier, JoinType, NodeType, QEPModification, ScanType
    from src.database.qep.qep_parser import QEPParser
    from src.database.qep.qep_visualizer import QEPVisualizer
    from src.settings.filepaths import VIZ_DIR
    from src.database.databaseManager import DatabaseManager
    from src.types.qep_types import NodeType, ScanType, JoinType
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
    original_graph: nx.DiGraph = parser.parse(qep_data)
    QEPVisualizer(original_graph).visualize(VIZ_DIR / "original_qep.png")

    # 3. Create modifications
    # Change the sequential scan on customer table to a bitmap index scan
    scan_modification = QEPModification(
        node_type=NodeType.SCAN,
        original_type=ScanType.SEQ_SCAN.value,
        new_type=ScanType.BITMAP_HEAP_SCAN.value,
        tables={'customer'},
        node_id="SOMESTRING"
    )

    # Change the nested loop join to a hash join
    join_modification = QEPModification(
        node_type=NodeType.JOIN,
        original_type=JoinType.HASH_JOIN.value,
        new_type=JoinType.NESTED_LOOP.value,
        tables={'customer', 'orders', "lineitem", "supplier"},
        node_id="SOMESTRING"
    )

    # 4. Apply modifications
    modifier = QEPModifier(original_graph)
    modifier.add_modification(scan_modification)
    modifier.add_modification(join_modification)

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

    modified_graph: nx.DiGraph = modifier.apply_modifications(False)
    QEPVisualizer(modified_graph).visualize(VIZ_DIR / "modified_pre-explained_qep_tree.png")

    # 5 Generate Hint
    hint = HintConstructor(modified_graph).generate_hints(query)
    print(hint)

    # 6 Modify Query (pre-pend hint)
    modified_query = QueryModifier(
        query=query,
        hint=hint
    ).modify()
    print(modified_query)

    # 7. Visualize the modified graph
    res = db_manager.get_qep(modified_query)
    q = QEPParser()
    tree = q.parse(res)
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    QEPVisualizer(tree).visualize(VIZ_DIR / "modified_explained_qep_tree.png")