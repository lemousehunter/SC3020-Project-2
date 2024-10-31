// mockData.ts
export const mockQEPData = {
  query: 'SELECT * FROM customer C, orders O WHERE C.c_custkey = O.o_custkey',
  nodes: [
    { id: 1, type: 'Sequential Scan', table: 'orders', cost: 150 },
    { id: 2, type: 'Hash Join', joinOn: 'c_custkey = o_custkey', cost: 300 },
    { id: 3, type: 'Index Scan', table: 'customer', cost: 100 },
  ],
  totalCost: 550,
};

export const mockAQPData = {
  query: 'SELECT * FROM customer C, orders O WHERE C.c_custkey = O.o_custkey',
  nodes: [
    { id: 1, type: 'Index Scan', table: 'orders', cost: 90 },
    { id: 2, type: 'Merge Join', joinOn: 'c_custkey = o_custkey', cost: 200 },
    { id: 3, type: 'Index Scan', table: 'customer', cost: 100 },
  ],
  totalCost: 390,
};
