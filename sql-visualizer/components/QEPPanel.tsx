// components/QEPPanel.tsx
'use client';

import { useState } from 'react';
import { Box, Button, Card, List, Select, Text, Title } from '@mantine/core';
import { mockQEPData } from './mockData';

interface QEPPanelProps {
  applyWhatIfChanges: (newSQL: string) => void; // Function to update modified SQL
}

export default function QEPPanel({ applyWhatIfChanges }: QEPPanelProps) {
  const [joinType, setJoinType] = useState<string | null>(null);
  const [scanType, setScanType] = useState<string | null>(null);
  const [qepData, setQepData] = useState(mockQEPData);

  const applyModifications = () => {
    // Generate a modified SQL query based on the selected join and scan types
    let modifiedSQL = `
      SELECT *
      FROM customer C
      ${joinType || 'Hash Join'} orders O ON C.c_custkey = O.o_custkey
    `;

    if (scanType === 'Index Scan') {
      modifiedSQL += '\nUSING INDEX';
    }

    // Update the mock QEP data to reflect the modifications
    const modifiedQEPData = {
      ...qepData,
      nodes: qepData.nodes.map((node) => {
        if (node.type === 'Hash Join' && joinType) {
          return { ...node, type: joinType };
        }
        if (node.type === 'Seq Scan' && scanType) {
          return {
            ...node,
            type: scanType,
            cost: scanType === 'Index Scan' ? node.cost - 50 : node.cost + 50,
          };
        }
        return node;
      }),
    };

    setQepData(modifiedQEPData);
    applyWhatIfChanges(modifiedSQL.trim());
  };

  return (
    <Card shadow="sm" padding="lg" mt="md">
      <Title order={4}>QEP Panel</Title>
      <Text mt="sm">Query: {qepData.query}</Text>
      <Text mt="sm">Total Cost: {qepData.totalCost}</Text>

      {/* Displaying QEP nodes */}
      <List mt="sm" withPadding>
        {qepData.nodes.map((node) => (
          <List.Item key={node.id}>
            {node.type} on {node.table || node.joinOn} (Cost: {node.cost})
          </List.Item>
        ))}
      </List>

      {/* What-If Modifications Controls */}
      <Box mt="lg">
        <Select
          label="Join Type"
          placeholder="Select join type"
          data={['Hash Join', 'Merge Join', 'Nested Loop']}
          value={joinType}
          onChange={setJoinType}
          mt="md"
        />
        <Select
          label="Scan Type"
          placeholder="Select scan type"
          data={['Sequential Scan', 'Index Scan']}
          value={scanType}
          onChange={setScanType}
          mt="md"
        />
        <Button mt="md" onClick={applyModifications}>
          Generate AQP
        </Button>
      </Box>
    </Card>
  );
}
