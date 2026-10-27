import type { ReactNode } from 'react'
import { Card } from './Card'

export function StatTile({ label, value, icon, accent = 'leaf' }: {
  label: string
  value: string | number
  icon: ReactNode
  accent?: 'leaf' | 'cherry' | 'forest'
}) {
  return (
    <Card className="p-4">
      <div className={`stat-icon stat-icon-${accent}`} aria-hidden>{icon}</div>
      <p className="mt-4 font-display text-4xl font-semibold leading-none text-soil">{value}</p>
      <p className="mt-2 text-xs font-medium leading-snug text-soil/60">{label}</p>
    </Card>
  )
}
