import { useState } from 'react'
import { useLocation } from 'wouter'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useStrategies, useCatalogBarTypes } from '@/hooks/use-strategies'
import { useCreateBacktest } from '@/hooks/use-mutations'

export const CreateBacktestPage = () => {
  const [, setLocation] = useLocation()
  const { data: strategies, isLoading: loadingStrategies } = useStrategies()
  const { data: barTypes, isLoading: loadingBarTypes } = useCatalogBarTypes()
  const createMutation = useCreateBacktest()

  const [strategy, setStrategy] = useState('')
  const [barType, setBarType] = useState('')
  const [params, setParams] = useState<Record<string, unknown>>({})

  const handleStrategyChange = (name: string) => {
    setStrategy(name)
    const info = strategies?.find((s) => s.name === name)
    if (info) setParams({ ...info.default_params })
  }

  const handleParamChange = (key: string, value: string) => {
    setParams((prev) => {
      if (value === 'true' || value === 'false') return { ...prev, [key]: value === 'true' }
      const num = Number(value)
      return { ...prev, [key]: isNaN(num) ? value : num }
    })
  }

  const handleSubmit = () => {
    if (!strategy || !barType) return
    createMutation.mutate(
      { strategy, bar_type: barType, params },
      { onSuccess: (data) => setLocation(`/runs/${data.run_id}`) },
    )
  }

  if (loadingStrategies || loadingBarTypes) return <div className="p-6">Loading...</div>

  return (
    <div className="space-y-6 p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">Create Backtest</h1>

      <Card>
        <CardHeader><CardTitle>Strategy</CardTitle></CardHeader>
        <CardContent>
          <select
            className="w-full p-2 border rounded bg-background"
            value={strategy}
            onChange={(e) => handleStrategyChange(e.target.value)}
          >
            <option value="">Select a strategy...</option>
            {strategies?.map((s) => (
              <option key={s.name} value={s.name}>{s.label}</option>
            ))}
          </select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Bar Data</CardTitle></CardHeader>
        <CardContent>
          <select
            className="w-full p-2 border rounded bg-background"
            value={barType}
            onChange={(e) => setBarType(e.target.value)}
          >
            <option value="">Select bar type...</option>
            {barTypes?.map((bt) => (
              <option key={bt} value={bt}>{bt}</option>
            ))}
          </select>
        </CardContent>
      </Card>

      {strategy && Object.keys(params).length > 0 && (
        <Card>
          <CardHeader><CardTitle>Parameters</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(params).map(([key, value]) => (
              <div key={key} className="flex items-center gap-4">
                <label className="w-48 text-sm font-medium text-muted-foreground">{key}</label>
                {typeof value === 'boolean' ? (
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(e) => setParams((prev) => ({ ...prev, [key]: e.target.checked }))}
                  />
                ) : (
                  <input
                    className="flex-1 p-2 border rounded bg-background"
                    value={String(value)}
                    onChange={(e) => handleParamChange(key, e.target.value)}
                  />
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Button
        onClick={handleSubmit}
        disabled={!strategy || !barType || createMutation.isPending}
        className="w-full"
      >
        {createMutation.isPending ? 'Running backtest...' : 'Run Backtest'}
      </Button>

      {createMutation.isError && (
        <p className="text-red-500 text-sm">
          Error: {String((createMutation.error as Error)?.message ?? createMutation.error)}
        </p>
      )}
    </div>
  )
}
