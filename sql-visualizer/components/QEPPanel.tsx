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

  const treeContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (qepData) {
      const treeData = convertNetworkXToTree(qepData);
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

  const handleNodeClick = (node: any) => {
    const nodeId = node.data.id || 'Unknown ID';
    const nodeType = node.data.type || 'Unknown Type';
    const nodeCategory = node.data.join_or_scan || 'Unknown'; // Changed to join_or_scan

    setSelectedNode({ id: nodeId, type: nodeType, join_or_scan: nodeCategory });
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
    if (selectedNode && selectedNode.newType && selectedNode.join_or_scan !== 'Unknown') {
      const updatedTreeData = JSON.parse(JSON.stringify(modifiedTreeData));
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
      treeData.type = newType;
      treeData.name = newType;
    } else if (treeData.children) {
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
        tables: Array.isArray(node?.table) ? node.table : [node?.table || 'No tables'],
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
        const originalCost = responseData.cost_comparison?.original_cost || 0;
        const modifiedCost = responseData.cost_comparison?.modified_cost || 0;
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

  const renderQEPNode = ({ nodeDatum, hierarchyPointNode }: any) => {
    const isSelected = selectedNode && selectedNode.id === nodeDatum.id;
    const fillColor =
      nodeDatum.join_or_scan === 'Scan'
        ? '#FFD700'
        : nodeDatum.join_or_scan === 'Unknown'
          ? '#EAF6FB'
          : '#B0D4FF'; // Default color for other types// Use join_or_scan for color
    const strokeColor = isSelected && nodeDatum.join_or_scan !== 'Unknown' ? '#FF4500' : '#000';
    const textColor = '#000';

    const maxLineLength = 20;
    const splitTableText = Array.isArray(nodeDatum.table)
      ? nodeDatum.table
      : typeof nodeDatum.table === 'string'
        ? nodeDatum.table.match(new RegExp(`.{1,${maxLineLength}}`, 'g'))
        : ['No tables'];

    const baseHeight = 60;
    const lineHeight = 18;
    const totalHeight = baseHeight + splitTableText.length * lineHeight;

    return (
      <g onClick={() => handleNodeClick(hierarchyPointNode)}>
        <rect
          x="-75"
          y={-totalHeight / 2}
          width="150"
          height={totalHeight}
          rx="15"
          fill={fillColor}
          stroke={strokeColor}
          strokeWidth={isSelected ? 3 : 1}
        />
        <text
          x="0"
          y={-totalHeight / 2 + 20}
          style={{ fontSize: 18, textAnchor: 'middle', fill: textColor }}
        >
          {nodeDatum.type}
        </text>
        <text
          x="0"
          y={-totalHeight / 2 + 40}
          style={{ fontSize: 16, textAnchor: 'middle', fill: textColor }}
        >
          Cost: {nodeDatum.cost}
        </text>
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

  const renderPreviewNode = ({ nodeDatum, hierarchyPointNode }: any) => {
    const isSelected = selectedNode && selectedNode.id === nodeDatum.id;
    const fillColor = nodeDatum.join_or_scan === 'Scan' ? '#EAF6FB' : '#B0D4FF'; // Use join_or_scan for color
    const strokeColor = isSelected && nodeDatum.join_or_scan !== 'Unknown' ? '#FF4500' : '#000';
    const textColor = '#000'; // Text color

    // Split table text into lines
    const maxLineLength = 20;
    const splitTableText = Array.isArray(nodeDatum.table)
      ? nodeDatum.table
      : nodeDatum.table.match(new RegExp(`.{1,${maxLineLength}}`, 'g')) || ['No tables'];

    // Calculate dynamic height based on table text
    const baseHeight = 60;
    const lineHeight = 18;
    const totalHeight = baseHeight + splitTableText.length * lineHeight;

    return (
      <g onClick={() => handleNodeClick(hierarchyPointNode)}>
        {/* Node rectangle */}
        <rect
          x="-75"
          y={-totalHeight / 2}
          width="150"
          height={totalHeight}
          rx="15"
          fill={fillColor}
          stroke={strokeColor}
          strokeWidth={isSelected ? 3 : 1}
        />
        {/* Node type */}
        <text
          x="0"
          y={-totalHeight / 2 + 20}
          style={{ fontSize: 18, textAnchor: 'middle', fill: textColor }}
        >
          {nodeDatum.type}
        </text>
        {/* Table text */}
        {splitTableText.map((line: string, index: number) => (
          <text
            key={index}
            x="0"
            y={-totalHeight / 2 + 50 + index * lineHeight}
            style={{ fontSize: 16, textAnchor: 'middle', fill: textColor }}
          >
            {index === 0 ? `Table: ${line}` : line}
          </text>
        ))}
      </g>
    );
  };

  return (
    <Card shadow="sm" padding="lg" mt="md" style={{ height: '98%', position: 'relative' }}>
      <Title order={4}>QEP Panel</Title>
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
                separation={{ siblings: 2, nonSiblings: 2.5 }}
                renderCustomNodeElement={renderQEPNode}
                collapsible={false}
              />
              {totalCostOriginalQEP !== null && (
                <Text mt="sm" align="center" style={{ fontWeight: 'bold' }}>
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
                    separation={{ siblings: 2, nonSiblings: 2.5 }}
                    renderCustomNodeElement={renderQEPNode} // Assuming renderQEPNode can handle generated AQP nodes
                    collapsible={false}
                  />
                  {totalCostAQP !== null && (
                    <Text mt="sm" align="center" style={{ fontWeight: 'bold' }}>
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
                    separation={{ siblings: 2, nonSiblings: 2.5 }}
                    renderCustomNodeElement={renderPreviewNode}
                    collapsible={false}
                  />
                  {totalCostAQP !== null && (
                    <Text mt="sm" align="center" style={{ fontWeight: 'bold' }}>
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
          {selectedNode && selectedNode.join_or_scan !== 'Unknown' && (
            <Group spacing="sm">
              {selectedNode.join_or_scan === 'Scan' ? (
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
          <Title order={5}>Hints</Title>
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
