// utils/convertToTree.ts
import { NetworkXData, Node } from './types';

export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  networkXData.nodes.forEach((node: any) => {
    const costLabel = `Cost: ${node.cost}`;
    const tableLabel = node.table ? ` (${node.table})` : ''; // Only add table in parentheses if it exists
    const label = `${node.type} (${costLabel})${tableLabel}`; // Place cost first, then table if it exists

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
