// Define interfaces for Node and Edge
interface AQPEdge {
  source: string;
  target: string;
}

interface AQPNode {
  _id: string;
  node_type: string;
  _join_or_scan?: string;
  cost?: number | string;
  tables: string[];
  isLeaf?: boolean;
  isRoot?: boolean;
  conditions?: string[];
  [key: string]: any; // Allow dynamic properties
}

interface AQPData {
  nodes: AQPNode[];
  edges: AQPEdge[];
}

export function convertAQPToTree(aqpData: AQPData) {
  const nodeMap = new Map<string, AQPNode & { children: AQPNode[] }>();

  // Step 1: Initialize nodes in the map
  aqpData.nodes.forEach((node: AQPNode) => {
    // Extracting visible attributes
    const visibleAttributes = Object.keys(node)
      .filter((key) => !key.startsWith('_') && key !== 'tables' && key !== 'children')
      .reduce((acc: any, key) => {
        acc[key] = node[key];
        return acc;
      }, {});

    // Prepare tables display
    const maxLineLength = 40;
    const tableText = Array.isArray(node.tables) ? node.tables.join(', ') : 'No tables';
    const splitTableText = tableText.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || [];

    // Add node to the map
    nodeMap.set(node._id, {
      id: node._id,
      node_type: node.node_type,
      _join_or_scan: node._join_or_scan || 'Unknown',
      cost: node.cost || 'N/A',
      tables: splitTableText,
      isLeaf: node.isLeaf || false,
      isRoot: node.isRoot || false,
      ...visibleAttributes, // Add the remaining visible attributes
      children: [], // Initialize children
    });
  });

  // Step 2: Create edges (parent-child relationships)
  aqpData.edges.forEach((edge: AQPEdge) => {
    const parent = nodeMap.get(edge.source);
    const child = nodeMap.get(edge.target);
    if (parent && child) {
      parent.children.push(child);
    } else {
      console.warn(`Edge connection issue - Parent or Child not found for edge:`, edge);
    }
  });

  // Step 3: Identify the root node using the `isRoot` field
  const rootNode = Array.from(nodeMap.values()).find((node) => node.is_root);

  if (!rootNode) {
    console.warn('Root node not found. Using fallback node.');
  } else {
    console.log('Root node:', rootNode);
  }

  // Debugging output for final structure
  console.log('NodeMap structure:', Array.from(nodeMap.values()));

  // Step 4: Return the tree starting from the root node
  return rootNode;
}
