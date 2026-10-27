import { IconArrowUpRight as ArrowUpRight } from '../icons'
import { Link } from 'react-router-dom'
import type { FarmerAlert } from '../../types'
import { Card } from './Card'
import { SeverityPill, type Severity } from './SeverityPill'

function severityOf(value: FarmerAlert['severity']): Severity {
  if (value === 'URGENT' || value === 'HIGH' || value === 'CRITICAL') return 'urgent'
  if (value === 'WATCH' || value === 'MEDIUM') return 'watch'
  return 'info'
}

export function AlertCard({ alert, language = 'en' }: { alert: FarmerAlert; language?: 'en' | 'sw' | 'guz' }) {
  return (
    <Card className="flex items-start gap-3 p-4">
      <span className={`alert-mark alert-mark-${severityOf(alert.severity)}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <SeverityPill severity={severityOf(alert.severity)} />
          <span className="font-mono text-xs text-soil/50">
            {new Date(alert.created_at).toLocaleDateString()}
          </span>
        </div>
        <h3 className="font-semibold leading-snug text-soil">{alert.title}</h3>
        {alert.body_by_language?.[language] && (
          <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-soil/65">
            {alert.body_by_language[language]}
          </p>
        )}
        <Link to="/alerts" className="mt-3 inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-forest">
          See advice <ArrowUpRight size={16} aria-hidden />
        </Link>
      </div>
    </Card>
  )
}
