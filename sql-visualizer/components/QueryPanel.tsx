// components/QueryPanel.tsx
'use client';

import { useState } from 'react';
import { Box, Button, Textarea, Title } from '@mantine/core';

interface QueryPanelProps {
  onSubmit: () => void;
}

export default function QueryPanel({ onSubmit }: QueryPanelProps) {
  const [query, setQuery] = useState<string>('');

  const handleQuerySubmit = () => {
    onSubmit(); // This should trigger handleQuerySubmit in HomePage
    console.log('Submitted Query:', query);
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
