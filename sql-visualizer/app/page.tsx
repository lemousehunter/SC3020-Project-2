'use client';

import { AppShell, Box, Divider, Grid, Group, Stack, Tabs, Title } from '@mantine/core';
import AQPPanel from '../components/AQPPanel';
import { ColorSchemeToggle } from '../components/ColorSchemeToggle/ColorSchemeToggle';
import QEPPanel from '../components/QEPPanel';
import QueryPanel from '../components/QueryPanel';
import { Welcome } from '../components/Welcome/Welcome';
import WhatIfPanel from '../components/WhatIfPanel';

export default function HomePage() {
  return (
    <AppShell
      padding="md"
      // Replacing Header with Box to simulate a header
      header={
        <Box
          sx={{
            padding: '10px 20px',
            borderBottom: '1px solid #e9ecef',
            backgroundColor: '#f8f9fa',
          }}
        >
          <Group position="apart">
            <Title order={3}>What-If Analysis of Query Plans</Title>
            <ColorSchemeToggle />
          </Group>
        </Box>
      }
    >
      <Stack spacing="md">
        {/* Welcome component as an introduction at the top */}
        <Welcome />

        <Divider mt="sm" mr="xl" ml="xl" />

        <Grid mr="xl" ml="xl">
          {/* Left side: Query Panel */}
          <Grid.Col span={4}>
            <QueryPanel />
          </Grid.Col>

          {/* Right side: Tabs for QEP, What-If, and AQP Panels */}
          <Grid.Col span={8}>
            <Tabs defaultValue="qep">
              <Tabs.List>
                <Tabs.Tab value="qep">QEP Panel</Tabs.Tab>
                <Tabs.Tab value="whatIf">What-If Panel</Tabs.Tab>
                <Tabs.Tab value="aqp">AQP Panel</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="qep" pt="sm">
                <QEPPanel />
              </Tabs.Panel>

              <Tabs.Panel value="whatIf" pt="sm">
                <WhatIfPanel />
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
