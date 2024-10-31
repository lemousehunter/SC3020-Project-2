'use client';

import { useEffect, useState } from 'react';
import { AppShell, Box, Divider, Grid, Group, Select, Stack, Tabs } from '@mantine/core';
import AQPPanel from '../components/AQPPanel';
import { ColorSchemeToggle } from '../components/ColorSchemeToggle/ColorSchemeToggle';
import ModifiedSQLPanel from '../components/ModifiedSQLPanel';
import QEPPanel from '../components/QEPPanel';
import QueryPanel from '../components/QueryPanel';
import { Welcome } from '../components/Welcome/Welcome';

export default function HomePage() {
  const [selectedDatabase, setSelectedDatabase] = useState<string | null>(null);
  const [databases, setDatabases] = useState<{ value: string; label: string }[]>([]);

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

    // Send selected database to backend
    fetch('/api/database/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ database: value }),
    })
      .then((response) => response.json())
      .then((data) => console.log(data.message))
      .catch((error) => console.error('Error setting selected database:', error));
  };

  return (
    <AppShell
      padding="md"
      styles={{
        main: {
          height: '100vh', // Full viewport height
          overflowY: 'auto', // Enables scrolling for long content
        },
      }}
    >
      <Stack spacing="md">
        {/* Welcome component as an introduction at the top */}
        <Welcome />

        <Box style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <Select
            label="Database"
            placeholder="Select database"
            data={databases}
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
            <QueryPanel />
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
                <QEPPanel />
              </Tabs.Panel>

              <Tabs.Panel value="whatIf" pt="sm">
                <ModifiedSQLPanel />
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
