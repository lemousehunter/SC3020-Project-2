// utils/convertToTree.ts
import { NetworkXData, Node } from './types';

export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  networkXData.nodes.forEach((node: any) => {
    const costLabel = `${node.cost}`;
    const tableLabel = node.table ? `\n${node.table}` : ''; // Add newline if table exists
    const label = `${node.type} (${costLabel})\n${tableLabel}`; // Place cost first, then table on new line if it exists

    nodeMap.set(node.id, {
      name: label,
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
