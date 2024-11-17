// HomePage Component
'use client';

import { useEffect, useState } from 'react';
import { IconX, IconCheck } from '@tabler/icons-react';
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
  Modal,
  Loader,
    useMantineColorScheme,
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
  const [query, setQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false); // Loading state

  const { setColorScheme } = useMantineColorScheme(); // Destructure the setColorScheme function

  useEffect(() => {
    // Set the color scheme to dark on component mount
    setColorScheme('dark');
  }, [setColorScheme]); // Run only once when the component mounts

  useEffect(() => {
    fetch('http://127.0.0.1:5000/api/database/available')
      .then((response) => response.json())
      .then((data) => setDatabases(data.databases))
      .catch((error) => console.error('Error fetching databases:', error));
  }, []);

  const handleDatabaseSelect = async (value: string | null) => {
    console.log(value);
    if (!value) {
      setNotification({ message: 'Please select a database.', show: true });
      return;
    }

    setLoading(true); // Show loading modal

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
      setLoading(false); // Hide loading modal
    } catch (error) {
      console.error('Error selecting database:', error);
      setNotification({
        message: 'Error selecting database. Please try again later.',
        show: true,
      });
    }
  };

  const handleQuerySubmit = async (query: string) => {
    setQuery(query);
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

      console.log(data);

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
            icon={
              notification.message.includes('successfully') ? (
                <IconCheck style={{ width: rem(20), height: rem(20) }} />
              ) : (
                <IconX style={{ width: rem(20), height: rem(20) }} />
              )
            } // Use IconCheck for success
            color={notification.message.includes('successfully') ? 'green' : 'red'} // Use green for success
            title={notification.message.includes('successfully') ? 'Success' : 'Error'} // Set title accordingly
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

        {/* Loading Modal */}
        <Modal opened={loading} onClose={() => {}} withCloseButton={false} centered>
          <Stack align="center" justify="center" spacing="xs">
            <Loader size="lg" />
            <Text>Loading, please wait...</Text>
          </Stack>
        </Modal>

        {notification.show && (
          <Notification
            icon={<IconX style={{ width: rem(20), height: rem(20) }} />}
            color={notification.message.includes('successfully') ? 'green' : 'red'} // Use green for success
            title={notification.message.includes('successfully') ? 'Success' : 'Error'} // Set title accordingly
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
            data={databases}
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
            <QueryPanel onSubmit={handleQuerySubmit} isDisabled={!!qepData} />
            <Divider mt="md" />
            <ModifiedSQLPanel modifiedSQL={modifiedSQL} />
          </Grid.Col>

          {/* Right side: QEP Panel or Message */}
          <Grid.Col span={8} mt="lg">
            {selectedDatabase && qepData ? (
              <QEPPanel applyWhatIfChanges={applyWhatIfChanges} qepData={qepData} query={query} />
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
