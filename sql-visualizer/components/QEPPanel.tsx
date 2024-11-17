import { useEffect, useRef, useState } from 'react';
import { IconCheck, IconInfoCircle, IconX } from '@tabler/icons-react';
import Tree from 'react-d3-tree';
import {
  Blockquote,
  Box,
  Button,
  Card,
  Divider,
  Group,
  HoverCard,
  Notification,
  Select,
  Switch,
  Text,
  Title,
} from '@mantine/core';
import { convertNetworkXToTree } from './convertToTree';

import './custom-tree.css';

import { convertAQPToTree } from './convertAQPToTree';

interface QEPPanelProps {
  applyWhatIfChanges: (newSQL: string) => void;
  qepData: any | null;
  query: string; // Add query as a prop
}
type SelectedNode = { id: string; type: string } | null;
type SelectedNodeOrderChange = { id: string; type: string }[];

export default function QEPPanel({ applyWhatIfChanges, qepData, query }: QEPPanelProps) {
  const [qepTreeData, setQepTreeData] = useState<any | null>(null);
  const [modifiedTreeData, setModifiedTreeData] = useState<any | null>(null);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [pendingChanges, setPendingChanges] = useState<
    { id: string; newType: string; originalType: string }[]
  >([]);
  const [showErrorNotification, setShowErrorNotification] = useState(false);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);
  const [qepTranslate, setQepTranslate] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [aqpTranslate, setAqpTranslate] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [qepZoom, setQepZoom] = useState(0.8); // Initial zoom level for QEP
  const [aqpZoom, setAqpZoom] = useState(0.8); // Initial zoom level for AQP
  const [modifiedSQL, setModifiedSQL] = useState<string>('');
  const [totalCostOriginalQEP, setTotalCostOriginalQEP] = useState<number | null>(null);
  const [generatedAQPData, setGeneratedAQPData] = useState<any | null>(null);
  const [apiHints, setApiHints] = useState<{ [key: string]: string }>({});

  const [totalCostAQP, setTotalCostAQP] = useState<number | null>(null);
  const [modificationType, setModificationType] = useState<'TypeChange' | 'OrderChange'>(
    'TypeChange'
  );
  const [firstSelectedNode, setFirstSelectedNode] = useState<any | null>(null);

  const treeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (qepData) {
      const treeData = convertNetworkXToTree(qepData);
      console.log(treeData);
      setQepTreeData(treeData);
      setModifiedTreeData(JSON.parse(JSON.stringify(treeData)));
    }
  }, [qepData]);

  useEffect(() => {
    if (treeContainerRef.current) {
      const { clientWidth, clientHeight } = treeContainerRef.current;

      if (pendingChanges.length > 0 || generatedAQPData) {
        setQepTranslate({ x: clientWidth / 5, y: clientHeight / 5 });
        setAqpTranslate({ x: clientWidth / 5, y: clientHeight / 5 });
      } else {
        setQepTranslate({ x: clientWidth / 2.2, y: clientHeight / 5 });
      }
    }
  }, [qepTreeData, pendingChanges]);

  const findParentNode = (tree: any, targetId: string): any | null => {
    if (!tree.children || tree.children.length === 0) {
      return null;
    }

    for (let child of tree.children) {
      if (child.id === targetId) {
        return tree; // Parent node found
      }

      const found = findParentNode(child, targetId);
      if (found) {
        return found;
      }
    }

    return null;
  };

  const getSiblingNode = (tree: any, currentNodeId: string): any | null => {
    const parentNode = findParentNode(tree, currentNodeId);

    if (!parentNode || !parentNode.children) {
      return null; // No parent or siblings found
    }

    // Filter siblings to exclude the current node and any with `_is_subquery_node` set to true
    const siblings = parentNode.children.filter(
      (child: any) => child.id !== currentNodeId && !child._is_subquery_node
    );

    return siblings.length > 0 ? siblings[0] : null; // Return the first valid sibling if found
  };

  const handleNodeClick = (node: any) => {
    if (modificationType === 'OrderChange') {
      if (firstSelectedNode === null) {
        // Set the first selected node
        setFirstSelectedNode(node.data);
      }

      // Only allow selecting swappable nodes based on criteria
      setSelectedNode((prev: SelectedNodeOrderChange | null) => {
        const prevArray = Array.isArray(prev) ? prev : []; // Ensure prev is an array
        if (prevArray.some((n) => n.id === node.data.id)) {
          // Deselect if the node is already selected
          return prevArray.filter((n) => n.id !== node.data.id);
        }
        if (prevArray.length < 2) {
          return [...prevArray, { id: node.data.id, type: node.data.type }];
        }
        return prevArray; // Keep as-is if already 2 nodes selected
      });
    } else if (modificationType === 'TypeChange') {
      if (node.data._join_or_scan !== 'Unknown') {
        setSelectedNode({
          id: node.data.id,
          type: node.data.type,
          _join_or_scan: node.data._join_or_scan,
        });
      }
    }
  };

  // Helper function to determine if a node should be disabled
  const isNodeDisabled = (nodeDatum: any) => {
    if (!firstSelectedNode) {
      return false; // No nodes are disabled before the first selection
    }

    const isFirstJoinNode = firstSelectedNode._join_or_scan === 'Join';
    const isCurrentJoinNode = nodeDatum._join_or_scan === 'Join';

    if (isFirstJoinNode) {
      // Enable only join nodes, itself, and its sibling
      return !(isCurrentJoinNode || nodeDatum.id === firstSelectedNode.id || isSibling(nodeDatum));
    } else {
      // Enable only itself and its sibling
      return !(nodeDatum.id === firstSelectedNode.id || isSibling(nodeDatum));
    }
  };

  const handleScanChange = (value: string | null) => {
    if (value !== null) {
      setSelectedNode((prevNode: any) => ({ ...prevNode, newType: value }));
    }
  };

  const handleJoinChange = (value: string | null) => {
    if (value !== null) {
      setSelectedNode((prevNode: any) => ({ ...prevNode, newType: value }));
    }
  };

  const confirmChange = () => {
    if (selectedNode && selectedNode.newType && selectedNode._join_or_scan !== 'Unknown') {
      const updatedTreeData = JSON.parse(JSON.stringify(modifiedTreeData)); // Clone tree to apply changes
      updateTreeData(updatedTreeData, selectedNode.id, selectedNode.newType);
      setModifiedTreeData(updatedTreeData);

      setPendingChanges((prevChanges) => [
        ...prevChanges,
        {
          id: selectedNode.id,
          newType: selectedNode.newType,
          originalType: selectedNode.type,
        },
      ]);

      setSelectedNode(null);
    }
  };

  const updateTreeData = (treeData: any, nodeId: string, newType: string) => {
    if (treeData.id === nodeId) {
      // Update the node type
      treeData.node_type = newType;
    } else if (treeData.children && treeData.children.length > 0) {
      // Recursively update child nodes
      treeData.children.forEach((child: any) => updateTreeData(child, nodeId, newType));
    }
  };

  const findNodeById = (treeNode: any, id: string): any | null => {
    if (treeNode.id === id) return treeNode;
    if (treeNode.children) {
      for (let child of treeNode.children) {
        const result = findNodeById(child, id);
        if (result) return result;
      }
    }
    return null;
  };

  const generateAQP = async () => {
    if (pendingChanges.length === 0) {
      setShowErrorNotification(true);
      setTimeout(() => setShowErrorNotification(false), 3000);
      return;
    }

    const modifications = pendingChanges.map((change) => {
      const node = findNodeById(modifiedTreeData, change.id);
      return {
        node_type: node?.type?.toUpperCase() || 'N/A', // Maps `join_or_scan` to `node_type`
        original_type: change.originalType,
        new_type: change.newType,
        mod_type: 'TypeChange',
        node_id: change.id,
      };
    });

    const requestBody = {
      query,
      modifications,
    };

    console.log(requestBody);

    try {
      const response = await fetch('http://127.0.0.1:5000/api/query/modify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        const responseData = await response.json();

        console.log('API Response:', responseData);

        const modifiedSql = responseData.modified_sql_query || '';
        const originalCost = responseData.cost_comparison?.original || 'Error';
        const modifiedCost = responseData.cost_comparison?.modified || 'Error';
        const updatedNetworkXObject = responseData.updated_networkx_object;
        const hints = responseData.hints || {};

        if (!updatedNetworkXObject) {
          console.error('Error: updated_networkx_object is missing from the response.');
          setShowErrorNotification(true);
          setNotification({
            message:
              'Error: updated_networkx_object is missing in the response. Please check with the API.',
            show: true,
          });
          return;
        }

        setModifiedSQL(modifiedSql);
        setTotalCostOriginalQEP(originalCost);
        setTotalCostAQP(modifiedCost);
        setApiHints(hints);

        applyWhatIfChanges(modifiedSql);

        console.log(updatedNetworkXObject);

        const aqpTreeData = convertAQPToTree(updatedNetworkXObject);
        setGeneratedAQPData(aqpTreeData);

        setPendingChanges([]);
        setShowSuccessNotification(true);
      } else {
        throw new Error('Failed to generate AQP');
      }
    } catch (error) {
      console.error('Error generating AQP:', error);
      setShowErrorNotification(true);
      setNotification({
        message: 'Error generating AQP. Please try again later or check the server logs.',
        show: true,
      });
    }
  };

  const previewOrderChange = (node: any) => {
    // Add logic to modify the node's order or mark the node for order preview.
    setPendingChanges((prevChanges) => [
      ...prevChanges,
      {
        id: node.id,
        newOrder: 'SomeOrderLogic', // Replace with actual logic to determine new order
        originalOrder: node.type,
        mod_type: 'OrderChange',
      },
    ]);
    setSelectedNode(null); // Deselect node after change
  };

  const getRenderQEPNode = () => {
    if (modificationType === 'OrderChange') {
      // Return the Order Change renderer
      return ({ nodeDatum, hierarchyPointNode }: any) => {
        const isSelected =
          Array.isArray(selectedNode) && selectedNode.some((node) => node.id === nodeDatum.id);

        const fillColor = !nodeDatum._swappable
          ? '#D3D3D3'
          : nodeDatum._join_or_scan === 'Scan'
            ? '#FFD700'
            : nodeDatum._join_or_scan === 'Unknown'
              ? '#EAF6FB'
              : '#B0D4FF';

        const strokeColor = isSelected ? '#FF4500' : '#000';
        const textColor = '#000';

        const allowedAttributes = [
          'node_type',
          'cost',
          'join_on',
          'Hash Cond',
          'join_order',
          'position',
        ];
        const displayAttributes = Object.entries(nodeDatum)
          .filter(([key]) => allowedAttributes.includes(key))
          .map(([key, value]) => ({ key, value }));

        const rowHeight = 20;
        const tablePadding = 10;

        const maxKeyLength = Math.max(...displayAttributes.map((attr) => attr.key.length));
        const maxValueLength = Math.max(
          ...displayAttributes.map((attr) => String(attr.value).length)
        );
        const calculatedWidth = Math.max(200, (maxKeyLength + maxValueLength) * 8);

        const totalHeight = tablePadding * 2 + displayAttributes.length * rowHeight + 20;

        return (
          <g
            onClick={() => {
              if (nodeDatum._swappable) {
                handleNodeClick(hierarchyPointNode);
              }
            }}
          >
            <rect
              x={-calculatedWidth / 2 - tablePadding}
              y={-totalHeight / 2}
              width={calculatedWidth + tablePadding * 2}
              height={totalHeight}
              rx="10"
              fill={fillColor}
              stroke={strokeColor}
              strokeWidth={isSelected ? 3 : 1}
            />
            <text
              x="0"
              y={-totalHeight / 2 + tablePadding + rowHeight / 2}
              style={{ fontSize: 16, textAnchor: 'middle', fill: textColor }}
            >
              {nodeDatum.node_type || 'Unknown Type'}
            </text>
            {displayAttributes.map((attr, index) => (
              <g key={index}>
                <text
                  x={-calculatedWidth / 2 + tablePadding}
                  y={-totalHeight / 2 + tablePadding + (index + 1) * rowHeight + rowHeight / 2}
                  style={{ fontSize: 15, textAnchor: 'start', fill: textColor }}
                >
                  {attr.key}:
                </text>
                <text
                  x={calculatedWidth / 2 - tablePadding}
                  y={-totalHeight / 2 + tablePadding + (index + 1) * rowHeight + rowHeight / 2}
                  style={{ fontSize: 15, textAnchor: 'end', fill: textColor }}
                >
                  {String(attr.value)}
                </text>
              </g>
            ))}
          </g>
        );
      };
    } else {
      // Return the Type Change renderer
      return ({ nodeDatum, hierarchyPointNode }: any) => {
        const isSelected = selectedNode && selectedNode.id === nodeDatum.id;

        const fillColor =
          nodeDatum._join_or_scan === 'Scan'
            ? '#FFD700'
            : nodeDatum._join_or_scan === 'Unknown'
              ? '#EAF6FB'
              : '#B0D4FF';

        const strokeColor = isSelected ? '#FF4500' : '#000';
        const textColor = '#000';

        const allowedAttributes = [
          'node_type',
          'cost',
          'join_on',
          'Hash Cond',
          'join_order',
          'position',
        ];
        const displayAttributes = Object.entries(nodeDatum)
          .filter(([key]) => allowedAttributes.includes(key))
          .map(([key, value]) => ({ key, value }));

        const rowHeight = 20;
        const tablePadding = 10;

        const maxKeyLength = Math.max(...displayAttributes.map((attr) => attr.key.length));
        const maxValueLength = Math.max(
          ...displayAttributes.map((attr) => String(attr.value).length)
        );
        const calculatedWidth = Math.max(200, (maxKeyLength + maxValueLength) * 8);

        const totalHeight = tablePadding * 2 + displayAttributes.length * rowHeight + 20;

        return (
          <g
            onClick={() => {
              if (nodeDatum._join_or_scan !== 'Unknown') {
                handleNodeClick(hierarchyPointNode);
              }
            }}
          >
            <rect
              x={-calculatedWidth / 2 - tablePadding}
              y={-totalHeight / 2}
              width={calculatedWidth + tablePadding * 2}
              height={totalHeight}
              rx="10"
              fill={fillColor}
              stroke={strokeColor}
              strokeWidth={isSelected ? 3 : 1}
            />
            <text
              x="0"
              y={-totalHeight / 2 + tablePadding + rowHeight / 2}
              style={{ fontSize: 16, textAnchor: 'middle', fill: textColor }}
            >
              {nodeDatum.node_type || 'Unknown Type'}
            </text>
            {displayAttributes.map((attr, index) => (
              <g key={index}>
                <text
                  x={-calculatedWidth / 2 + tablePadding}
                  y={-totalHeight / 2 + tablePadding + (index + 1) * rowHeight + rowHeight / 2}
                  style={{ fontSize: 15, textAnchor: 'start', fill: textColor }}
                >
                  {attr.key}:
                </text>
                <text
                  x={calculatedWidth / 2 - tablePadding}
                  y={-totalHeight / 2 + tablePadding + (index + 1) * rowHeight + rowHeight / 2}
                  style={{ fontSize: 15, textAnchor: 'end', fill: textColor }}
                >
                  {String(attr.value)}
                </text>
              </g>
            ))}
          </g>
        );
      };
    }
  };

  const renderPreviewNode = ({ nodeDatum }: any) => {
    const fillColor =
      nodeDatum._join_or_scan === 'Scan'
        ? '#FFD700'
        : nodeDatum._join_or_scan === 'Unknown'
          ? '#EAF6FB'
          : '#B0D4FF'; // Use join_or_scan for color
    const strokeColor = '#000'; // Default stroke color (no selection for preview)
    const textColor = '#000'; // Default text color

    // Attributes to display, excluding `cost`
    const allowedAttributes = ['node_type', 'join_on', 'Hash Cond', 'join_order', 'position'];
    const displayAttributes = Object.entries(nodeDatum)
      .filter(([key]) => allowedAttributes.includes(key))
      .map(([key, value]) => ({ key, value }));

    const baseHeight = 60; // Base height for the rectangle
    const lineHeight = 18; // Line height for each attribute
    const totalHeight = baseHeight + displayAttributes.length * lineHeight;

    return (
      <g>
        {/* Node rectangle */}
        <rect
          x="-75"
          y={-totalHeight / 2}
          width="150"
          height={totalHeight}
          rx="15"
          fill={fillColor}
          stroke={strokeColor}
          strokeWidth={1}
        />
        {/* Node type at the top */}
        <text
          x="0"
          y={-totalHeight / 2 + 20}
          style={{ fontSize: 18, textAnchor: 'middle', fill: textColor }}
        >
          {nodeDatum.node_type || 'Unknown Type'}
        </text>
        {/* Dynamically render additional attributes */}
        {displayAttributes.map((attr, index) => (
          <text
            key={index}
            x="0"
            y={-totalHeight / 2 + 40 + index * lineHeight}
            style={{ fontSize: 14, textAnchor: 'middle', fill: textColor }}
          >
            {`${attr.key}: ${attr.value}`}
          </text>
        ))}
      </g>
    );
  };

  return (
    <Card shadow="sm" padding="lg" mt="md" style={{ height: '98%', position: 'relative' }}>
      <Box
        style={{
          display: 'flex',
          justifyContent: 'space-between', // Align items to the left and right
          alignItems: 'center', // Vertically center items
          width: '100%',
        }}
      >
        {/* Title */}
        <Title order={4}>QEP Panel</Title>

        {/* Slide Toggle */}
        <Switch
          label={modificationType === 'TypeChange' ? 'Type Change' : 'Order Change'}
          checked={modificationType === 'OrderChange'}
          onChange={(event) =>
            setModificationType(event.currentTarget.checked ? 'OrderChange' : 'TypeChange')
          }
          size="md"
        />
      </Box>
      <Text>
        Visualized Query Execution Plan (QEP): Drag the tree or pinch to zoom for better view
      </Text>

      <Box
        mt="md"
        ref={treeContainerRef}
        style={{
          display: 'flex',
          flexDirection: 'row',
          gap: '20px',
          width: '100%',
          backgroundColor: 'rgb(203 213 225)',
          padding: '20px',
          borderRadius: '8px',
        }}
      >
        <Box
          style={{
            width: pendingChanges.length > 0 || generatedAQPData ? '50%' : '100%',
            height: '450px',
            padding: '10px',
          }}
        >
          <Title order={5} style={{ color: 'black' }}>
            Original QEP
          </Title>
          {qepTreeData ? (
            <>
              <Tree
                data={qepTreeData}
                orientation="vertical"
                pathFunc="straight"
                translate={qepTranslate}
                zoom={qepZoom}
                nodeSize={{ x: 120, y: 200 }}
                separation={{ siblings: 2, nonSiblings: 3 }}
                renderCustomNodeElement={getRenderQEPNode()} // Dynamically apply the renderer
                collapsible={false}
              />
              {totalCostOriginalQEP !== null && (
                <Text mt="sm" align="center">
                  Total Cost: {totalCostOriginalQEP}
                </Text>
              )}
            </>
          ) : (
            <Text style={{ color: 'grey' }}>Loading original QEP...</Text>
          )}
        </Box>

        {(pendingChanges.length > 0 || generatedAQPData) && (
          <>
            <Divider
              orientation="vertical"
              style={{ height: '100%', flexShrink: 0, margin: '0 10px', backgroundColor: 'black' }}
            />
            <Box style={{ width: '50%', padding: '10px', height: '450px' }}>
              <Title order={5} style={{ color: 'black' }}>
                {generatedAQPData ? 'Generated AQP' : 'Preview of AQP'}
              </Title>
              {generatedAQPData ? (
                <>
                  <Tree
                    data={generatedAQPData} // Use the generated AQP data
                    orientation="vertical"
                    pathFunc="straight"
                    translate={aqpTranslate}
                    zoom={aqpZoom}
                    nodeSize={{ x: 120, y: 200 }}
                    separation={{ siblings: 2, nonSiblings: 2.5 }}
                    renderCustomNodeElement={renderQEPNode} // Assuming renderQEPNode can handle generated AQP nodes
                    collapsible={false}
                  />
                  {totalCostAQP !== null && (
                    <Text mt="sm" align="center">
                      Total Cost: {totalCostAQP}
                    </Text>
                  )}
                </>
              ) : modifiedTreeData ? (
                <>
                  <Tree
                    data={modifiedTreeData} // Use the modified preview data
                    orientation="vertical"
                    pathFunc="straight"
                    translate={aqpTranslate}
                    zoom={aqpZoom}
                    nodeSize={{ x: 120, y: 200 }}
                    separation={{ siblings: 2, nonSiblings: 2.5 }}
                    renderCustomNodeElement={renderPreviewNode}
                    collapsible={false}
                  />
                  {totalCostAQP !== null && (
                    <Text mt="sm" align="center">
                      Total Cost: {totalCostAQP}
                    </Text>
                  )}
                </>
              ) : (
                <Text style={{ color: 'grey' }}>Loading modified QEP...</Text>
              )}
            </Box>
          </>
        )}
      </Box>

      {!generatedAQPData && (
        <Box mt="md" style={{ display: 'flex', justifyContent: 'space-between' }}>
          {selectedNode && selectedNode._join_or_scan !== 'Unknown' && (
            <Group spacing="sm">
              <Group spacing="sm">
                {modificationType === 'TypeChange' ? (
                  selectedNode._join_or_scan === 'Scan' ? (
                    <Select
                      label="Change Scan Type"
                      placeholder="Select scan type"
                      data={[
                        'Seq Scan',
                        'Index Scan',
                        'Index Only Scan',
                        'Bitmap Heap Scan',
                        'Tid Scan',
                      ]}
                      value={selectedNode.newType || ''}
                      onChange={handleScanChange}
                    />
                  ) : (
                    <Select
                      label="Change Join Type"
                      placeholder="Select Join Type"
                      data={['Hash Join', 'Merge Join', 'Nested Loop']}
                      value={selectedNode.newType || ''}
                      onChange={handleJoinChange}
                    />
                  )
                ) : (
                  <Button onClick={() => previewOrderChange(selectedNode)}>
                    Preview Order Change
                  </Button>
                )}

                {modificationType === 'TypeChange' && (
                  <Box style={{ alignSelf: 'flex-end' }}>
                    <Button onClick={confirmChange}>Confirm Change</Button>
                  </Box>
                )}
              </Group>
            </Group>
          )}

          {/* Generate AQP Button */}
          <Box style={{ alignSelf: 'flex-end', marginLeft: 'auto', marginTop: '25px' }}>
            <Button
              color="#CE3F44"
              onClick={generateAQP}
              style={{ width: '150px' }}
              disabled={pendingChanges.length === 0}
            >
              Generate AQP
            </Button>
          </Box>
        </Box>
      )}

      {showErrorNotification && (
        <Notification
          color="red"
          icon={<IconX size={18} />}
          title="Error"
          style={{
            position: 'fixed',
            bottom: 20,
            left: 20,
          }}
          onClose={() => setShowErrorNotification(false)}
        >
          An error occurred while sending the AQP data.
        </Notification>
      )}

      {showSuccessNotification && (
        <Notification
          color="teal"
          icon={<IconCheck size={18} />}
          title="Success"
          style={{
            position: 'fixed',
            bottom: 20,
            left: 20,
          }}
          onClose={() => setShowSuccessNotification(false)}
        >
          The AQP was generated successfully.
        </Notification>
      )}

      {!selectedNode && pendingChanges.length === 0 && !generatedAQPData && (
        <Box
          style={{
            position: 'absolute',
            bottom: '65px',
            left: '20px',
            width: '300px',
          }}
        >
          <Blockquote color="red" style={{ fontSize: '14px', padding: '5px 10px' }}>
            Click on a node to start modifying the tree.
          </Blockquote>
        </Box>
      )}

      {generatedAQPData && (
        <Box mt="xl">
          <Title order={5} mt="xl">
            Hints
          </Title>
          <Group mt="sm">
            {Object.entries(apiHints).map(([key, value]) => (
              <HoverCard width={280} shadow="md" key={key}>
                <HoverCard.Target>
                  <Button variant="light" size="xs">
                    {key}
                  </Button>
                </HoverCard.Target>
                <HoverCard.Dropdown>
                  <Text size="sm">{value}</Text>
                </HoverCard.Dropdown>
              </HoverCard>
            ))}
          </Group>
        </Box>
      )}
    </Card>
  );
}
