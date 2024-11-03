export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  networkXData.nodes.forEach((node: any) => {
    const maxLineLength = 35;
    const tableText = node.table || 'No tables';
    const splitTableText = tableText.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || [];

    nodeMap.set(node.id, {
      id: node.id,
      type: node.type,
      node_type: node.node_type || (node.isLeaf ? 'LEAF' : 'INTERNAL'), // Default node type
      cost: node.cost || 'N/A',
      table: splitTableText,
      isLeaf: node.isLeaf || false,
      isRoot: node.isRoot || false,
      conditions: node.conditions || [],
      children: [],
    });
  });

  networkXData.edges.forEach((edge: any) => {
    const parent = nodeMap.get(edge.source);
    const child = nodeMap.get(edge.target);
    if (parent && child) {
      parent.children.push(child);
    }
  });

  // Find the root node dynamically
  const rootNode = Array.from(nodeMap.values()).find((node: any) => node.isRoot);
  return rootNode || nodeMap.values().next().value; // Return root or fallback to the first node
}
