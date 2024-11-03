export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  // Step 1: Initialize nodes in the map
  networkXData.nodes.forEach((node: any) => {
    const maxLineLength = 40;
    const tableText = node.tables.join(', ') || 'No tables';
    const splitTableText = tableText.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || [];

    nodeMap.set(node.id, {
      id: node.id,
      type: node.type,
      join_or_scan: node.join_or_scan || 'Unknown',
      cost: node.cost || 'N/A',
      table: splitTableText,
      isLeaf: node.isLeaf || false,
      isRoot: node.isRoot || false,
      conditions: node.conditions || [],
      children: [], // Initialize children as an empty array
    });
  });

  // Step 2: Create edges (parent-child relationships)
  networkXData.edges.forEach((edge: any) => {
    const parent = nodeMap.get(edge.source);
    const child = nodeMap.get(edge.target);
    if (parent && child) {
      parent.children.push(child);
    }
  });

  // Step 3: Identify the root node using the `isRoot` field
  const rootNode = Array.from(nodeMap.values()).find((node) => node.isRoot);

  // Step 4: Return the tree starting from the root node
  return rootNode || nodeMap.values().next().value; // Return root or fallback to the first node if none found
}
