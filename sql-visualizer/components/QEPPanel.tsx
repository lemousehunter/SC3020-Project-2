// components/QEPPanel.tsx
'use client';

import { useEffect, useState } from 'react';
import Tree from 'react-d3-tree';
import { Box, Button, Card, Select, Text, Title } from '@mantine/core';
import { convertNetworkXToTree } from './convertToTree';

interface QEPPanelProps {
  applyWhatIfChanges: (newSQL: string) => void;
  qepData: any | null;
}

export default function QEPPanel({ applyWhatIfChanges, qepData }: QEPPanelProps) {
  const [qepTreeData, setQepTreeData] = useState<any | null>(null);

  useEffect(() => {
    if (qepData) {
      // Assume convertNetworkXToTree is a function that converts qepData into tree format
      const treeData = convertNetworkXToTree(qepData);
      setQepTreeData(treeData);
    }
  }, [qepData]);

  return (
    <Card shadow="sm" padding="lg" mt="md">
      <Title order={4}>QEP Panel</Title>
      <Text mt="sm">Visualized Query Execution Plan (QEP):</Text>
      <Box
        mt="md"
        style={{
          height: '400px',
          width: '100%',
          backgroundColor: 'rgb(203 213 225)',
          padding: '20px',
          borderRadius: '8px',
        }}
      >
        {qepTreeData ? (
          <Tree
            data={qepTreeData}
            orientation="vertical"
            pathFunc="straight"
            translate={{ x: 250, y: 100 }} // Adjust starting position if necessary
            separation={{ siblings: 2, nonSiblings: 2.5 }} // Increase separation between nodes
            styles={{
              links: { stroke: '#999', strokeWidth: 2 },
              nodes: {
                node: { circle: { fill: '#4285f4', stroke: 'black' }, name: { fontSize: 12 } }, // Optional: Adjust font size
                leafNode: { circle: { fill: '#4285f4', stroke: 'black' }, name: { fontSize: 12 } },
              },
            }}
          />
        ) : (
          <Text>Submit a query to display QEP</Text>
        )}
      </Box>
    </Card>
  );
}
