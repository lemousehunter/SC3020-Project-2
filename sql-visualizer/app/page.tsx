// HomePage Component
'use client';

import { useEffect, useState } from 'react';
import { IconX } from '@tabler/icons-react';
import {
  AppShell,
  Box,
  Divider,
  Grid,
  Notification,
  rem,
  Select,
  Stack,
  Tabs,
} from '@mantine/core';
import AQPPanel from '../components/AQPPanel';
import { ColorSchemeToggle } from '../components/ColorSchemeToggle/ColorSchemeToggle';
import ModifiedSQLPanel from '../components/ModifiedSQLPanel';
import QEPPanel from '../components/QEPPanel';
import QueryPanel from '../components/QueryPanel';
import { Welcome } from '../components/Welcome/Welcome';

export default function HomePage() {
  const [selectedDatabase, setSelectedDatabase] = useState<string | null>(null);
  const [databases, setDatabases] = useState<{ value: string; label: string }[]>([]);
  const [modifiedSQL, setModifiedSQL] = useState<string>('');
  const [qepData, setQepData] = useState<any | null>(null);
  const [notification, setNotification] = useState<{ message: string; show: boolean }>({
    message: '',
    show: false,
  }); // Notification state

  // Mock QEP Data for demonstration
  const mockQEPNetworkXData = {
    nodes: [
      { id: '1', type: 'Hash Join', table: null, cost: 200 },
      { id: '2', type: 'Seq Scan', table: 'customer', cost: 100 },
      { id: '3', type: 'Hash', table: null, cost: 150 },
      { id: '4', type: 'Seq Scan', table: 'orders', cost: 100 },
    ],
    edges: [
      { source: '1', target: '2' },
      { source: '1', target: '3' },
      { source: '3', target: '4' },
    ],
  };

  // Fetch available databases on component mount
  useEffect(() => {
    fetch('/api/database/available')
      .then((response) => response.json())
      .then((data) => setDatabases(data.databases))
      .catch((error) => console.error('Error fetching databases:', error));
  }, []);

  // Handle database selection
  const handleDatabaseSelect = (value: string | null) => {
    setSelectedDatabase(value);
    setNotification((prev) => ({ ...prev, show: false })); // Hide notification if a database is selected
  };

  // Handle query submission
  const handleQuerySubmit = (query: string) => {
    if (!selectedDatabase) {
      setNotification({
        message: 'Please select a database before submitting the query.',
        show: true,
      });
      return;
    }

    if (!query.trim()) {
      setNotification({ message: 'Please enter a query before submitting.', show: true });
      return;
    }

    // // Send query to backend with the selected database in the URL
    // fetch(`/api/query/execute?database=${selectedDatabase}`, {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ query }),
    // })
    //   .then((response) => {
    //     if (!response.ok) {
    //       throw new Error('Failed to fetch QEP data');
    //     }
    //     return response.json();
    //   })
    //   .then((data) => {
    //     setQepData(data.qepData); // Update with backend response
    //   })
    //   .catch((error) => {
    //     console.error('Error fetching QEP data:', error);
    //   });
    setQepData(mockQEPNetworkXData);
  };

  const applyWhatIfChanges = (newSQL: string) => {
    setModifiedSQL(newSQL);
  };

  return (
    <AppShell
      padding="md"
      styles={{
        main: {
          height: '100vh',
          overflowY: 'auto',
        },
      }}
    >
      <Stack spacing="md">
        {/* Welcome component as an introduction at the top */}
        <Welcome />

        {/* Floating Notification for missing database or query */}
        {notification.show && (
          <Notification
            icon={<IconX style={{ width: rem(20), height: rem(20) }} />}
            color="red"
            title="Error"
            onClose={() => setNotification((prev) => ({ ...prev, show: false }))}
            style={{
              position: 'fixed',
              bottom: rem(20),
              left: rem(20),
              width: rem(300),
              zIndex: 1000,
            }}
          >
            {notification.message}
          </Notification>
        )}

        <Box style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <Select
            label="Database"
            placeholder="Select database"
            data={[
              { value: 'postgresql', label: 'TPC-H' },
              { value: 'mysql', label: 'TPC-A' },
              { value: 'oracle', label: 'TPC-B' },
              { value: 'sqlserver', label: 'TPC-L' },
            ]}
            //data={databases}
            value={selectedDatabase}
            onChange={handleDatabaseSelect}
            searchable
            clearable
            style={{ width: '430px' }}
          />
        </Box>

        <Divider mt="sm" mr="xl" ml="xl" />

        <Grid mr="xl" ml="xl">
          {/* Left side: Query Panel */}
          <Grid.Col span={4}>
            <QueryPanel onSubmit={handleQuerySubmit} /> {/* Pass handleQuerySubmit to QueryPanel */}
          </Grid.Col>

          {/* Right side */}
          <Grid.Col span={8}>
            <Tabs defaultValue="qep">
              <Tabs.List>
                <Tabs.Tab value="qep">QEP Panel</Tabs.Tab>
                <Tabs.Tab value="whatIf">Modified SQL Panel</Tabs.Tab>
                <Tabs.Tab value="aqp">AQP Panel</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="qep" pt="sm">
                <QEPPanel applyWhatIfChanges={applyWhatIfChanges} qepData={qepData} />
              </Tabs.Panel>

              <Tabs.Panel value="whatIf" pt="sm">
                <ModifiedSQLPanel modifiedSQL={modifiedSQL} />
              </Tabs.Panel>

              <Tabs.Panel value="aqp" pt="sm">
                <AQPPanel />
              </Tabs.Panel>
            </Tabs>
          </Grid.Col>
        </Grid>
      </Stack>
    </AppShell>
  );
}
