// components/ModifiedSQLPanel.tsx
'use client';

import { Box, Code, Text, Title } from '@mantine/core';

interface ModifiedSQLPanelProps {
  modifiedSQL: string;
}

export default function ModifiedSQLPanel({ modifiedSQL }: ModifiedSQLPanelProps) {
  return (
    <Box>
      <Title order={4}>Modified SQL Query</Title>
      <Text mt="sm">Here is the SQL query generated based on your modifications:</Text>
      <Box mt="lg">
        <Code block>{modifiedSQL}</Code>
      </Box>
    </Box>
  );
}
