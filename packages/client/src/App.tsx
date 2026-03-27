import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Route, Switch } from 'wouter'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AppLayout } from '@/components/layout/AppLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { RunDetailPage } from '@/pages/RunDetailPage'
import { CreateBacktestPage } from '@/pages/CreateBacktestPage'
import { InstrumentPage } from '@/pages/InstrumentPage'

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
          <Route path="/create" component={CreateBacktestPage} />
          <Route path="/instruments/:barType">
            {(params) => <InstrumentPage barType={params.barType} />}
          </Route>
        </Switch>
      </AppLayout>
    </TooltipProvider>
  </QueryClientProvider>
)

export default App
