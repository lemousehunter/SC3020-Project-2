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
  Text,
  Title,
} from '@mantine/core';
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
    sql_query:
      'SELECT /*+ Leading( ( ( (l s) o) c) )  NestLoop( c o l s) HashJoin( l s ) HashJoin( l o ) BitmapScan(c) */ * FROM customer C, orders O, lineitem L, supplier S WHERE C.c_custkey = O.o_custkey AND O.o_orderkey = L.l_orderkey AND L.l_suppkey = S.s_suppkey AND L.l_quantity > (SELECT AVG(L2.l_quantity) FROM lineitem L2 WHERE L2.l_suppkey = S.s_suppkey)',
    cost: 35594434.57,
    message: 'Query plan generated successfully',
    networkx_object: {
      nodes: [
        {
          id: 'fc357241-d4b4-4caf-8e6f-9a2d07030f12',
          isLeaf: true,
          isRoot: false,
          type: 'Seq Scan',
          table: 'lineitem',
          tables: ['lineitem'],
          cost: 172517.16,
          conditions: [],
        },
        {
          id: '254c0f89-aa03-4e22-a716-cedd7c551885',
          isLeaf: false,
          isRoot: true,
          type: 'Hash Join',
          tables: ['lineitem', 'supplier'],
          cost: 27742206.55,
          conditions: [
            '(lineitem.l_suppkey = supplier.s_suppkey)',
            '(lineitem.l_quantity > (SubPlan 1))',
          ],
        },
      ],
      edges: [
        {
          source: '254c0f89-aa03-4e22-a716-cedd7c551885',
          target: 'fc357241-d4b4-4caf-8e6f-9a2d07030f12',
        },
      ],
    },
    status: 'success',
  };

  useEffect(() => {
    fetch('http://127.0.0.1:5000/api/database/available')
      .then((response) => response.json())
      .then((data) => setDatabases(data.databases))
      .catch((error) => console.error('Error fetching databases:', error));
  }, []);

  const handleDatabaseSelect = async (value: string | null) => {
    if (!value) {
      setNotification({ message: 'Please select a database.', show: true });
      return;
    }

    try {
      // Send the selected database to the backend API
      const response = await fetch('http://127.0.0.1:5000/api/database/select', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ database: value }), // Send selected database as JSON
      });

      // Check if the response is successful
      if (!response.ok) {
        throw new Error('Failed to select the database');
      }

      // Assuming the API response includes a message or some confirmation
      const data = await response.json();
      setNotification({ message: 'Database selected successfully!', show: true });

      // Update the selected database in the state
      setSelectedDatabase(value);
    } catch (error) {
      console.error('Error selecting database:', error);
      setNotification({
        message: 'Error selecting database. Please try again later.',
        show: true,
      });
    }
  };

  const handleQuerySubmit = async (query: string) => {
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

    try {
      // Send the query to the backend API
      const response = await fetch('http://127.0.0.1:5000/api/query/plan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }), // send query in the request body
      });

      // Check if the response is successful
      if (!response.ok) {
        throw new Error('Failed to fetch QEP data');
      }

      // Parse the response JSON
      const data = await response.json();

      // Assuming 'networkx_object' is the key containing the QEP data
      setQepData(data.networkx_object);
      setNotification({
        message: 'Query plan fetched successfully!',
        show: false,
      });
    } catch (error) {
      console.error('Error fetching QEP data:', error);
      setNotification({
        message: 'Error fetching QEP data. Please try again later.',
        show: true,
      });
    }
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

        <Grid mr="xl" ml="xl" mb="md">
          {/* Left side: Query Panel with Modified SQL Panel below */}
          <Grid.Col span={4}>
            <QueryPanel onSubmit={handleQuerySubmit} />
            <Divider mt="md" />
            <ModifiedSQLPanel modifiedSQL={modifiedSQL} />
          </Grid.Col>

          {/* Right side: QEP Panel or Message */}
          <Grid.Col span={8} mt="lg">
            {selectedDatabase && qepData ? (
              <QEPPanel applyWhatIfChanges={applyWhatIfChanges} qepData={qepData} />
            ) : (
              <Box
                style={{
                  height: '98%',
                  backgroundColor: '#2E2E2E',
                  borderRadius: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginTop: '16px',
                  color: '#555',
                }}
              >
                <Text>Please select a database and enter an SQL query to view the QEP.</Text>
              </Box>
            )}
          </Grid.Col>
        </Grid>
      </Stack>
    </AppShell>
  );
}
