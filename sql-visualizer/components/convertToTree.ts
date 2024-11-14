export function convertNetworkXToTree(networkXData: any) {
  const nodeMap = new Map();

  // Step 1: Initialize nodes in the map
  networkXData.nodes.forEach((node: any) => {
    // Extract visible attributes, excluding _id, is_root, children, and tables
    const visibleAttributes = Object.keys(node)
      .filter((key) => key !== 'id' && key !== 'is_root' && key !== 'tables' && key !== 'children')
      .reduce((acc: any, key) => {
        acc[key] = node[key];
        return acc;
      }, {});

    // Reorder so that 'node_type' is the first attribute
    const reorderedAttributes = {
      node_type: node.node_type,
      ...visibleAttributes,
    };

    nodeMap.set(node._id, {
      id: node._id,
      ...reorderedAttributes,
      children: [], // Initialize children
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

  // Step 3: Sort children based on position
  const sortNodesByPosition = (node: any) => {
    if (node.children) {
      const order: Record<'l' | 'c' | 'r' | 's', number> = { l: -1, c: 0, r: 1, s: 2 }; // Restrict types for position
      node.children.sort(
        (a: { position: 'l' | 'c' | 'r' | 's' }, b: { position: 'l' | 'c' | 'r' | 's' }) => {
          return order[a.position] - order[b.position];
        }
      );

      // Recursively sort child nodes
      node.children.forEach(sortNodesByPosition);
    }
    return node;
  };

  // Step 4: Identify the root node using the `is_root` field
  const rootNode = Array.from(nodeMap.values()).find((node) => node.isRoot);

  // Step 5: Sort the entire tree starting from the root
  return rootNode ? sortNodesByPosition(rootNode) : nodeMap.values().next().value;
}
