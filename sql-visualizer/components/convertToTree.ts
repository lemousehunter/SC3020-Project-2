// utils/convertToTree.ts
export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  networkXData.nodes.forEach((node: any) => {
    const tableLabel = node.table ? ` (${node.table})` : ''; // Only add table if it exists
    const label = `${node.type}${tableLabel}`; // Exclude cost from the label

    nodeMap.set(node.id, {
      id: node.id,
      type: node.type,
      name: label,
      children: [],
      isLeaf: node.isLeaf,
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
