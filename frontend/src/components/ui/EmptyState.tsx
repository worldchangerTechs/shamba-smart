import type { ReactNode } from 'react'

export function EmptyState({ icon, title, description, action }: {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon" aria-hidden>{icon}</div>
      <h3 className="font-display text-xl font-semibold text-soil">{title}</h3>
      <p className="mt-1 max-w-xs text-sm leading-relaxed text-soil/60">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
