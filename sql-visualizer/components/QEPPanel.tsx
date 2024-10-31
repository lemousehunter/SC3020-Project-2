'use client';

import { useEffect, useState } from 'react';
import { IconX } from '@tabler/icons-react';
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

  useEffect(() => {
    if (qepData) {
      const treeData = convertNetworkXToTree(qepData);
      setQepTreeData(treeData);
      setModifiedTreeData(JSON.parse(JSON.stringify(treeData))); // Initialize modifiedTreeData without costs
    }
  }, [qepData]);

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
      // Update the node name without including cost in the modified tree
      treeData.name = newType;
    } else if (treeData.children) {
      treeData.children.forEach((child: any) => updateTreeData(child, nodeId, newType));
    }
  };

  const generateAQP = () => {
    if (pendingChanges.length === 0) {
      setShowErrorNotification(true);
      setTimeout(() => setShowErrorNotification(false), 3000); // Hide notification after 3 seconds
      return;
    }

    const modifiedSQL = pendingChanges
      .map((change) => `Change node ${change.id} to ${change.newType}`)
      .join('\n');

    applyWhatIfChanges(modifiedSQL);
    setPendingChanges([]); // Clear pending changes after generating AQP
  };

  const renderCustomNode = ({ nodeDatum, hierarchyPointNode }: any) => {
    const isSelected = selectedNode && selectedNode.id === nodeDatum.id;

    return (
      <g>
        <circle
          r={15} // Make selected nodes slightly larger
          fill={nodeDatum.isLeaf ? (isSelected ? 'red' : 'white') : isSelected ? 'red' : 'black'}
          stroke={isSelected ? 'red' : 'black'}
          strokeWidth={isSelected ? 3 : 1}
          onClick={() => handleNodeClick(hierarchyPointNode)}
        />
        <text x={25} y={5} style={{ fontSize: 17, fill: isSelected ? 'red' : 'black' }}>
          {nodeDatum.name}
        </text>
      </g>
    );
  };

  return (
    <Card shadow="sm" padding="lg" mt="md">
      <Title order={4}>QEP Panel</Title>
      <Text>Visualized Query Execution Plan (QEP):</Text>

      {/* Container for the two side-by-side trees */}
      <Box
        mt="md"
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
        {/* Original QEP Tree */}
        <Box
          style={{
            width: pendingChanges.length > 0 ? '50%' : '100%',
            height: '350px',
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
              translate={{ x: 200, y: 50 }}
              separation={{ siblings: 2, nonSiblings: 2.5 }}
              renderCustomNodeElement={renderCustomNode}
              collapsible={false}
            />
          ) : (
            <Text style={{ color: 'grey' }}>Loading original QEP...</Text>
          )}
        </Box>

        {/* Only display the divider and modified QEP tree if there are modifications */}
        {pendingChanges.length > 0 && (
          <>
            {/* Vertical Divider */}
            <Divider
              orientation="vertical"
              style={{ height: '100%', flexShrink: 0, margin: '0 10px', backgroundColor: 'black' }}
            />

            {/* Modified QEP Tree */}
            <Box style={{ width: '50%', padding: '10px', height: '350px' }}>
              <Title order={5} style={{ color: 'black' }}>
                Modified QEP
              </Title>
              {modifiedTreeData ? (
                <Tree
                  data={modifiedTreeData}
                  orientation="vertical"
                  pathFunc="straight"
                  translate={{ x: 200, y: 50 }}
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

      {/* Modification controls */}
      {selectedNode && (
        <Box mt="md" mb="md">
          <Text>
            Modify Node: {selectedNode.type} (ID: {selectedNode.id})
          </Text>
          <Group mt="md" spacing="sm" align="flex-end">
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
            <Button onClick={confirmChange}>Confirm Change</Button>
          </Group>
        </Box>
      )}

      <Button
        mt="lg"
        color="blue"
        onClick={generateAQP}
        style={{ width: '150px', alignSelf: 'flex-start' }}
      >
        Generate AQP
      </Button>

      {showErrorNotification && (
        <Notification
          color="red"
          icon={<IconX size={18} />}
          title="No changes detected"
          style={{
            position: 'fixed',
            bottom: 20,
            left: 20,
          }}
          onClose={() => setShowErrorNotification(false)}
        >
          Please modify the scan or join type before generating AQP.
        </Notification>
      )}
    </Card>
  );
}
