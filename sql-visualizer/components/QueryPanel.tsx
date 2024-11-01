// components/QueryPanel.tsx
'use client';

import { useState } from 'react';
import { Box, Button, Textarea, Title } from '@mantine/core';

interface QueryPanelProps {
  onSubmit: (query: string) => void; // Update onSubmit to accept a query parameter
}

export default function QueryPanel({ onSubmit }: QueryPanelProps) {
  const [query, setQuery] = useState<string>('');

  const handleQuerySubmit = () => {
    onSubmit(query); // Pass the query to HomePage's handleQuerySubmit
  };

  return (
    <Box>
      <Title order={4}>Query Panel</Title>
      <Textarea
        placeholder="Enter your SQL query here"
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        autosize
        minRows={12}
        maxRows={150}
        mt="sm"
      />
      <Button mt="md" onClick={handleQuerySubmit}>
        Submit Query
      </Button>
    </Box>
  );
}
