// components/ModifiedSQLPanel.tsx
'use client';

import { Box, Code, Text, Textarea, Title } from '@mantine/core';

interface ModifiedSQLPanelProps {
  modifiedSQL: string;
}

export default function ModifiedSQLPanel({ modifiedSQL }: ModifiedSQLPanelProps) {
  return (
    <Box>
      <Title order={4} mt="md">
        Modified SQL Query
      </Title>
      <Box mt="lg">
        <Textarea
          value={modifiedSQL}
          readOnly
          minRows={12}
          maxRows={150}
          autosize
          style={{ width: '100%' }}
        />
      </Box>
    </Box>
  );
}
