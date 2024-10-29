import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import "./App.css";

function App() {
  const [sql, setSql] = useState("");
  const [planData, setPlanData] = useState(null);
  const [modifiedPlan, setModifiedPlan] = useState(null);
  const [comparison, setComparison] = useState(null);

  const handleAnalyze = () => {
    // TODO: Add actual PostgreSQL query plan fetching
    console.log("Analyzing query:", sql);
  };

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="container mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold">Query Plan Analyzer</h1>
          <p className="text-muted-foreground">
            Analyze and modify PostgreSQL query execution plans
          </p>
        </div>

        <ResizablePanelGroup
          direction="horizontal"
          className="min-h-[600px] rounded-lg border"
        >
          {/* Left Panel - Query Input */}
          <ResizablePanel defaultSize={40} minSize={30} maxSize={50}>
            <Card className="h-full rounded-none">
              <CardHeader>
                <CardTitle>SQL Query</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  placeholder="Enter your SQL query here..."
                  value={sql}
                  onChange={(e) => setSql(e.target.value)}
                  className="h-[200px] mb-4"
                />
                <Button onClick={handleAnalyze} className="w-full">
                  Analyze Query Plan
                </Button>
              </CardContent>
            </Card>
          </ResizablePanel>

          {/* Right Panel - Results */}
          <ResizablePanel defaultSize={60}>
            <Tabs defaultValue="qep" className="h-full">
              <TabsList className="w-full justify-start">
                <TabsTrigger value="qep">Query Execution Plan</TabsTrigger>
                <TabsTrigger value="modified">Modified Plan</TabsTrigger>
                <TabsTrigger value="comparison">Cost Comparison</TabsTrigger>
              </TabsList>

              <TabsContent value="qep" className="h-[calc(100%-40px)]">
                <Card className="h-full rounded-none border-t-0">
                  <CardContent className="p-4">
                    {planData ? (
                      <div className="h-full overflow-auto">
                        {/* TODO: Add tree visualization component */}
                        <pre>{JSON.stringify(planData, null, 2)}</pre>
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center">
                        <Alert>
                          <AlertTitle>No Query Plan Available</AlertTitle>
                          <AlertDescription>
                            Enter a SQL query and click "Analyze Query Plan" to
                            view the execution plan.
                          </AlertDescription>
                        </Alert>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="modified" className="h-[calc(100%-40px)]">
                <Card className="h-full rounded-none border-t-0">
                  <CardContent className="p-4">
                    {modifiedPlan ? (
                      <div className="h-full overflow-auto">
                        {/* TODO: Add interactive tree editor component */}
                        <pre>{JSON.stringify(modifiedPlan, null, 2)}</pre>
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center">
                        <Alert>
                          <AlertTitle>No Modified Plan</AlertTitle>
                          <AlertDescription>
                            Modify the query execution plan to see changes here.
                          </AlertDescription>
                        </Alert>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="comparison" className="h-[calc(100%-40px)]">
                <Card className="h-full rounded-none border-t-0">
                  <CardContent className="p-4">
                    {comparison ? (
                      <div className="h-full overflow-auto">
                        {/* TODO: Add cost comparison visualization */}
                        <pre>{JSON.stringify(comparison, null, 2)}</pre>
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center">
                        <Alert>
                          <AlertTitle>No Comparison Available</AlertTitle>
                          <AlertDescription>
                            Modify the query plan to see cost comparisons.
                          </AlertDescription>
                        </Alert>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </div>
  );
}

export default App;
