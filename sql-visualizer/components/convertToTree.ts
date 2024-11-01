export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  networkXData.nodes.forEach((node: any) => {
    // Define maximum line length for table text
    const maxLineLength = 35;

    // Split table text into multiple lines if it exceeds the maximum line length
    const tableText = node.table || 'No tables';
    const splitTableText = tableText.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || [];

    nodeMap.set(node.id, {
      id: node.id,
      type: node.type,
      cost: node.cost || 'N/A',
      table: splitTableText, // Store as an array of strings
      isLeaf: node.isLeaf,
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

  return nodeMap.get('1'); // Assuming '1' is the root node ID
}
