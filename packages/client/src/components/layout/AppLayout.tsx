import type { ReactNode } from 'react'
import { Link, useLocation } from 'wouter'
import { cn } from '@/lib/utils'

type NavItem = { readonly href: string; readonly label: string }

const NAV_ITEMS: readonly NavItem[] = [
  { href: '/', label: 'Runs' },
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

export const AppLayout = ({ children }: { readonly children: ReactNode }) => (
  <div className="min-h-screen bg-background">
    <header className="border-b border-border">
      <div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center gap-6">
        <Link href="/" className="text-lg font-bold text-foreground">
          Nautilus Automatron
        </Link>
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
