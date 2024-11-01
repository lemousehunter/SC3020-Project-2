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
  });

  const mockQEPNetworkXData = {
    nodes: [
      { id: '1', type: 'Hash Join', table: null, cost: 200, isLeaf: false },
      { id: '2', type: 'Seq Scan', table: 'customer', cost: 100, isLeaf: true },
      { id: '3', type: 'Hash', table: null, cost: 150, isLeaf: false },
      { id: '4', type: 'Seq Scan', table: 'orders', cost: 100, isLeaf: true },
    ],
    edges: [
      { source: '1', target: '2' },
      { source: '1', target: '3' },
      { source: '3', target: '4' },
    ],
  };

  useEffect(() => {
    fetch('/api/database/available')
      .then((response) => response.json())
      .then((data) => setDatabases(data.databases))
      .catch((error) => console.error('Error fetching databases:', error));
  }, []);

  const handleDatabaseSelect = (value: string | null) => {
    setSelectedDatabase(value);
    setNotification((prev) => ({ ...prev, show: false }));
  };

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
        <Welcome />

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
          {/* Left side: Query Panel with Modified SQL Panel below */}
          <Grid.Col span={4}>
            <QueryPanel onSubmit={handleQuerySubmit} />
            <Divider mt="md" />
            <ModifiedSQLPanel modifiedSQL={modifiedSQL} />{' '}
            {/* Modified SQL Panel under Query Panel */}
          </Grid.Col>

          {/* Right side: QEP and AQP Tabs */}
          <Grid.Col span={8}>
            <Tabs defaultValue="qep">
              <Tabs.List>
                <Tabs.Tab value="qep">QEP Panel</Tabs.Tab>
                <Tabs.Tab value="aqp">AQP Panel</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="qep" pt="sm">
                <QEPPanel applyWhatIfChanges={applyWhatIfChanges} qepData={qepData} />
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
