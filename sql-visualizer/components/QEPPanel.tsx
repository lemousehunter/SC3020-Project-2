'use client';

import { useEffect, useState } from 'react';
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

    // Send modified tree data to backend
    // try {
    //   const response = await fetch('/api/aqp/generate', {
    //     method: 'POST',
    //     headers: { 'Content-Type': 'application/json' },
    //     body: JSON.stringify({ modifiedTree: modifiedTreeData }),
    //   });

    //   if (response.ok) {
    //     setShowSuccessNotification(true);
    //     setModifiedTreeData(null); // Clear modified tree after success
    //     setPendingChanges([]);
    //   } else {
    //     throw new Error('Failed to send AQP data');
    //   }
    // } catch (error) {
    //   console.error('Error sending AQP data:', error);
    //   setShowErrorNotification(true);
    // } finally {
    //   // Hide notifications after 3 seconds
    //   setTimeout(() => {
    //     setShowErrorNotification(false);
    //     setShowSuccessNotification(false);
    //   }, 3000);
    // }
    setShowSuccessNotification(true);
  };

  const renderCustomNode = ({ nodeDatum, hierarchyPointNode }: any) => {
    const isSelected = selectedNode && selectedNode.id === nodeDatum.id;

    return (
      <g>
        <circle
          r={15}
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
    <Card shadow="sm" padding="lg" mt="md" style={{ height: '98%' }}>
      <Title order={4}>QEP Panel</Title>
      <Text>Visualized Query Execution Plan (QEP):</Text>

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
