// components/WhatIfPanel.tsx
'use client';

import { useState } from 'react';
import { Box, Button, Select, Text, Title } from '@mantine/core';

export default function WhatIfPanel() {
  const [joinType, setJoinType] = useState<string | null>(null);
  const [scanType, setScanType] = useState<string | null>(null);

  const applyModifications = () => {
    // Logic for applying modifications to QEP
    console.log('Selected Join Type:', joinType);
    console.log('Selected Scan Type:', scanType);
  };

  return (
    <Box>
      <Title order={4}>What-If Panel</Title>
      <Text mt="sm">Modify the QEP to pose what-if questions:</Text>
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
        Apply Modifications
      </Button>
    </Box>
  );
}
