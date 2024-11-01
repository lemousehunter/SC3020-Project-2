export function convertAQPToTree(aqpData: any) {
  const nodeMap = new Map();

  // Create nodes
  aqpData.nodes.forEach((node: any) => {
    const maxLineLength = 35;
    const tableText = node.table || 'No tables';
    const splitTableText = tableText.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || [];

    nodeMap.set(node.id, {
      id: node.id,
      type: node.type,
      node_type: node.node_type,
      cost: node.cost || 'N/A',
      table: splitTableText,
      children: [],
    });
  });

  // Link nodes based on edges
  aqpData.edges.forEach((edge: any) => {
    const parent = nodeMap.get(edge.source);
    const child = nodeMap.get(edge.target);
    if (parent && child) {
      parent.children.push(child);
    }
  });

  return nodeMap.get('1'); // Assuming '1' is the root node ID
}
