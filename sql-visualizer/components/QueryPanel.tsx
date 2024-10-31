// components/QueryPanel.tsx
'use client';

import { useState } from 'react';
import { Box, Button, Textarea, Title } from '@mantine/core';

export default function QueryPanel() {
  const [query, setQuery] = useState<string>('');

  const handleQuerySubmit = () => {
    // Logic for handling query submission
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
        minRows={3}
        maxRows={6}
        mt="sm"
      />
      <Button mt="md" onClick={handleQuerySubmit}>
        Submit Query
      </Button>
    </Box>
  );
}
