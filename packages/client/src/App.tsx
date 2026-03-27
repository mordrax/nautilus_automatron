import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Route, Switch } from 'wouter'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AppLayout } from '@/components/layout/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { RunDetailPage } from '@/pages/RunDetailPage'

const queryClient = new QueryClient()

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <AppLayout>
        <Switch>
          <Route path="/" component={DashboardPage} />
          <Route path="/runs/:runId">
            {(params) => <RunDetailPage runId={params.runId} />}
          </Route>
        </Switch>
      </AppLayout>
    </TooltipProvider>
  </QueryClientProvider>
)

export default App
