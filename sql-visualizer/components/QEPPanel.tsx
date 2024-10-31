// components/QEPPanel.tsx
import { Card, List, Text, Title } from '@mantine/core';
import { mockQEPData } from './mockData';

export default function QEPPanel() {
  return (
    <Card shadow="sm" padding="lg" mt="md">
      <Title order={4}>QEP Panel</Title>
      <Text mt="sm">Query: {mockQEPData.query}</Text>
      <Text mt="sm">Total Cost: {mockQEPData.totalCost}</Text>
      <List mt="sm" withPadding>
        {mockQEPData.nodes.map((node) => (
          <List.Item key={node.id}>
            {node.type} on {node.table || node.joinOn} (Cost: {node.cost})
          </List.Item>
        ))}
      </List>
    </Card>
  );
}
