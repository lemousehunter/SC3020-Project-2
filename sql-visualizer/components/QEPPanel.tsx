import { useEffect, useRef, useState } from 'react';
import { IconCheck, IconX } from '@tabler/icons-react';
import Tree from 'react-d3-tree';
import {
  Box,
  Button,
  Card,
  Divider,
  Group,
  Notification,
  Select,
  Text,
  Title,
} from '@mantine/core';
import { convertNetworkXToTree } from './convertToTree';

import './custom-tree.css';

interface QEPPanelProps {
  applyWhatIfChanges: (newSQL: string) => void;
  qepData: any | null;
}

export default function QEPPanel({ applyWhatIfChanges, qepData }: QEPPanelProps) {
  const [qepTreeData, setQepTreeData] = useState<any | null>(null);
  const [modifiedTreeData, setModifiedTreeData] = useState<any | null>(null);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [pendingChanges, setPendingChanges] = useState<{ id: string; newType: string }[]>([]);
  const [showErrorNotification, setShowErrorNotification] = useState(false);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);
  const [translate, setTranslate] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Ref to get the container dimensions
  const treeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (qepData) {
      const treeData = convertNetworkXToTree(qepData);
      setQepTreeData(treeData);
      setModifiedTreeData(JSON.parse(JSON.stringify(treeData))); // Initialize modifiedTreeData without costs
    }
  }, [qepData]);

  useEffect(() => {
    // Center the tree in the container when it first loads
    if (treeContainerRef.current) {
      const { clientWidth, clientHeight } = treeContainerRef.current;
      setTranslate({ x: clientWidth / 2.2, y: clientHeight / 5 });
    }
  }, [qepTreeData]);

  const handleNodeClick = (node: any) => {
    const nodeId = node.data.id || 'Unknown ID';
    const nodeType = node.data.type || 'Unknown Type';
    const isLeaf = node.data.isLeaf || false;

    setSelectedNode({ id: nodeId, type: nodeType, isLeaf });
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
    if (selectedNode && selectedNode.newType) {
      const updatedTreeData = JSON.parse(JSON.stringify(modifiedTreeData));
      updateTreeData(updatedTreeData, selectedNode.id, selectedNode.newType);
      setModifiedTreeData(updatedTreeData);

      setPendingChanges((prevChanges) => [
        ...prevChanges,
        { id: selectedNode.id, newType: selectedNode.newType },
      ]);
      setSelectedNode(null); // Clear selected node after confirming change
    }
  };

  const updateTreeData = (treeData: any, nodeId: string, newType: string) => {
    if (treeData.id === nodeId) {
      treeData.type = newType;
      treeData.name = newType;
    } else if (treeData.children) {
      treeData.children.forEach((child: any) => updateTreeData(child, nodeId, newType));
    }
  };

  const generateAQP = async () => {
    if (pendingChanges.length === 0) {
      setShowErrorNotification(true);
      setTimeout(() => setShowErrorNotification(false), 3000);
      return;
    }

    const modifiedSQL = pendingChanges
      .map((change) => `Change node ${change.id} to ${change.newType}`)
      .join('\n');

    applyWhatIfChanges(modifiedSQL);
    setShowSuccessNotification(true);
  };

  const renderCustomNode = ({ nodeDatum, hierarchyPointNode }: any) => {
    const isSelected = selectedNode && selectedNode.id === nodeDatum.id;

    // Node colors
    const fillColor = nodeDatum.isLeaf ? '#EAF6FB' : '#B0D4FF'; // Keep fill color consistent
    const strokeColor = isSelected ? '#FF4500' : '#000'; // Change stroke color when selected
    const textColor = '#000'; // Keep text color consistent

    // Adjust the table text to fit within a certain max line length
    const maxLineLength = 20; // Maximum number of characters per line
    const splitTableText = Array.isArray(nodeDatum.table)
      ? nodeDatum.table
      : nodeDatum.table.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || ['No tables'];

    // Calculate height dynamically based on the number of lines in the table text
    const baseHeight = 60; // Base height for the node without table text
    const lineHeight = 18;
    const totalHeight = baseHeight + splitTableText.length * lineHeight;

    return (
      <g onClick={() => handleNodeClick(hierarchyPointNode)}>
        {/* Node rectangle with dynamic height and stroke color */}
        <rect
          x="-75"
          y={-totalHeight / 2}
          width="150"
          height={totalHeight}
          rx="15"
          fill={fillColor}
          stroke={strokeColor}
          strokeWidth={isSelected ? 3 : 1} // Thicker stroke for selected node
        />
        {/* Node type */}
        <text
          x="0"
          y={-totalHeight / 2 + 20}
          style={{ fontSize: 20, textAnchor: 'middle', fill: textColor }}
        >
          {nodeDatum.type}
        </text>
        {/* Cost */}
        <text
          x="0"
          y={-totalHeight / 2 + 40}
          style={{ fontSize: 16, textAnchor: 'middle', fill: textColor }}
        >
          Cost: {nodeDatum.cost}
        </text>
        {/* Table text positioned dynamically based on total height */}
        {splitTableText.map((line: string, index: number) => (
          <text
            key={index}
            x="0"
            y={-totalHeight / 2 + 60 + index * lineHeight}
            style={{ fontSize: 16, textAnchor: 'middle', fill: textColor }}
          >
            {index === 0 ? `Table: ${line}` : line}
          </text>
        ))}
      </g>
    );
  };

  return (
    <Card shadow="sm" padding="lg" mt="md" style={{ height: '98%' }}>
      <Title order={4}>QEP Panel</Title>
      <Text>Visualized Query Execution Plan (QEP): Drag the tree for better view</Text>

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
            width: pendingChanges.length > 0 ? '50%' : '100%',
            height: '450px',
            padding: '10px',
          }}
        >
          <Title order={5} style={{ color: 'black' }}>
            Original QEP
          </Title>
          {qepTreeData ? (
            <Tree
              data={qepTreeData}
              orientation="vertical"
              pathFunc="straight"
              translate={translate}
              separation={{ siblings: 2, nonSiblings: 2.5 }}
              renderCustomNodeElement={renderCustomNode}
              collapsible={false}
            />
          ) : (
            <Text style={{ color: 'grey' }}>Loading original QEP...</Text>
          )}
        </Box>

        {pendingChanges.length > 0 && (
          <>
            <Divider
              orientation="vertical"
              style={{ height: '100%', flexShrink: 0, margin: '0 10px', backgroundColor: 'black' }}
            />
            <Box style={{ width: '50%', padding: '10px', height: '350px' }}>
              <Title order={5} style={{ color: 'black' }}>
                Modified QEP
              </Title>
              {modifiedTreeData ? (
                <Tree
                  data={modifiedTreeData}
                  orientation="vertical"
                  pathFunc="straight"
                  translate={translate}
                  separation={{ siblings: 2, nonSiblings: 2.5 }}
                  renderCustomNodeElement={renderCustomNode}
                  collapsible={false}
                />
              ) : (
                <Text style={{ color: 'grey' }}>Loading modified QEP...</Text>
              )}
            </Box>
          </>
        )}
      </Box>

      <Box mt="md" style={{ display: 'flex', justifyContent: 'space-between' }}>
        {selectedNode && (
          <Group spacing="sm">
            {selectedNode.isLeaf ? (
              <Select
                label="Change Scan Type"
                placeholder="Select scan type"
                data={['Seq Scan', 'Index Scan', 'Index Only Scan', 'Bitmap Heap Scan', 'Tid Scan']}
                value={selectedNode.newType || ''}
                onChange={handleScanChange}
              />
            ) : (
              <Select
                label="Change Join Type"
                placeholder="Select join type"
                data={['Hash Join', 'Merge Join', 'Nested Loop']}
                value={selectedNode.newType || ''}
                onChange={handleJoinChange}
              />
            )}
            <Box style={{ alignSelf: 'flex-end' }}>
              <Button onClick={confirmChange}>Confirm Change</Button>
            </Box>
          </Group>
        )}
        <Box style={{ alignSelf: 'flex-end', marginLeft: 'auto' }}>
          <Button color="#CE3F44" onClick={generateAQP} style={{ width: '150px' }}>
            Generate AQP
          </Button>
        </Box>
      </Box>

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
    </Card>
  );
}
