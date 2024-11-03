export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  // Step 1: Initialize nodes in the map
  networkXData.nodes.forEach((node: any) => {
    const maxLineLength = 35;
    const tableText = node.tables.join(', ') || 'No tables'; // Update based on your data
    const splitTableText = tableText.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || [];

    nodeMap.set(node.id, {
      id: node.id,
      type: node.type,
      join_or_scan: node.join_or_scan || 'Unknown',
      cost: node.cost || 'N/A',
      table: splitTableText,
      isLeaf: node.isLeaf || false,
      conditions: node.conditions || [],
      children: [], // Initialize children as an empty array
    });
  });

  // Step 2: Create edges (parent-child relationships)
  const childNodeIds = new Set();
  networkXData.edges.forEach((edge: any) => {
    const parent = nodeMap.get(edge.source);
    const child = nodeMap.get(edge.target);
    if (parent && child) {
      parent.children.push(child);
      childNodeIds.add(edge.target); // Track all nodes that are children
    }
  });

  // Step 3: Identify the root node (the one without incoming edges)
  const rootNode = Array.from(nodeMap.values()).find((node) => !childNodeIds.has(node.id));

  // Step 4: Return the tree starting from the root node
  return rootNode || nodeMap.values().next().value; // Return root or fallback to the first node if none found
}
