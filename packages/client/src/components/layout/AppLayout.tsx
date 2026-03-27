import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation } from 'wouter'
import { cn } from '@/lib/utils'
import { getVersion, ping, runEffect } from '@/lib/api'

type NavItem = { readonly href: string; readonly label: string }

const NAV_ITEMS: readonly NavItem[] = [
  { href: '/', label: 'Dashboard' },
]

const NavLink = ({ href, label }: NavItem) => {
  const [location] = useLocation()
  const isActive = location === href || (href !== '/' && location.startsWith(href))

  return (
    <Link
      href={href}
      className={cn(
        'px-3 py-2 rounded-md text-sm font-medium transition-colors',
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-accent',
      )}
    >
      {label}
    </Link>
  )
}

export const AppLayout = ({ children }: { readonly children: ReactNode }) => {
  const { data: versionData } = useQuery({
    queryKey: ['version'],
    queryFn: () => runEffect(getVersion()),
  })

  const { isSuccess: backendUp, isError: backendDown } = useQuery({
    queryKey: ['ping'],
    queryFn: () => runEffect(ping()),
    refetchInterval: 60_000,
    retry: false,
  })

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-block h-2.5 w-2.5 rounded-full',
                backendUp ? 'bg-green-500' : backendDown ? 'bg-red-500' : 'bg-gray-400',
              )}
              title={backendUp ? 'Backend connected' : backendDown ? 'Backend unreachable' : 'Checking...'}
            />
            <Link href="/" className="text-lg font-bold text-foreground">
              Nautilus Automatron{versionData ? ` (${versionData.version})` : ''}
            </Link>
          </div>
          <nav className="flex gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.href} {...item} />
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-screen-2xl mx-auto px-6 py-6">{children}</main>
    </div>
  )
}
