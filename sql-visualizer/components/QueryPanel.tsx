// components/QueryPanel.tsx
'use client';

import { useState } from 'react';
import { Box, Button, Textarea, Title } from '@mantine/core';

interface QueryPanelProps {
  onSubmit: (query: string) => void; // Update onSubmit to accept a query parameter
}

export default function QueryPanel({ onSubmit, isDisabled }: { onSubmit: (query: string) => void; isDisabled: boolean }) {
  const [queryInput, setQueryInput] = useState<string>('');

  const handleSubmit = () => {
    onSubmit(queryInput);
  };

  return (
    <Box>
      <Title order={4}>Query Panel</Title>
      <Textarea
        placeholder="Enter your SQL query here"
        value={queryInput}
        onChange={(e) => setQueryInput(e.currentTarget.value)}
        autosize
        minRows={12}
        maxRows={150}
        mt="sm"
      />
        <Button
        onClick={handleSubmit}
        disabled={isDisabled} // Disable the button when QEP data is loaded
        mt="sm"
      >
        Submit Query
      </Button>
    </Box>
  );
}

