// Define interfaces for Node and Edge
interface AQPEdge {
  source: string;
  target: string;
}

interface AQPNode {
  id: string;
  type: string;
  join_or_scan?: string;
  cost?: number | string;
  tables: string[];
  isLeaf?: boolean;
  isRoot?: boolean;
  conditions?: string[];
}

interface AQPData {
  nodes: AQPNode[];
  edges: AQPEdge[];
}

export function convertAQPToTree(aqpData: AQPData) {
  const nodeMap = new Map<string, AQPNode & { children: AQPNode[] }>();

  // Step 1: Initialize nodes in the map
  aqpData.nodes.forEach((node: AQPNode) => {
    const maxLineLength = 40;
    const tableText = Array.isArray(node.tables) ? node.tables.join(', ') : 'No tables';
    const splitTableText = tableText.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || [];

    nodeMap.set(node.id, {
      id: node.id,
      type: node.type,
      join_or_scan: node.join_or_scan || 'Unknown',
      cost: node.cost || 'N/A',
      tables: splitTableText,
      isLeaf: node.isLeaf || false,
      isRoot: node.isRoot || false,
      conditions: node.conditions || [],
      children: [], // Initialize children as an empty array
    });
  });

  // Step 2: Create edges (parent-child relationships)
  aqpData.edges.forEach((edge: AQPEdge) => {
    const parent = nodeMap.get(edge.source);
    const child = nodeMap.get(edge.target);
    if (parent && child) {
      parent.children.push(child);
    } else {
      console.warn(`Warning: Edge connection issue - Parent or Child not found for edge:`, edge);
    }
  });

  // Step 3: Identify the root node using the `isRoot` field
  const rootNode = Array.from(nodeMap.values()).find((node) => node.isRoot);

  if (!rootNode) {
    console.warn('Warning: Root node not found. Using fallback node.');
  }

  // Step 4: Debugging output for final node structure
  console.log('NodeMap structure with children populated:', Array.from(nodeMap.values()));

  // Verify if rootNode has children
  if (rootNode && rootNode.children.length === 0) {
    console.warn('Warning: Root node has no children.');
  }

  // Step 5: Return the tree starting from the root node
  return rootNode || nodeMap.values().next().value; // Return root or fallback to the first node if none found
}
