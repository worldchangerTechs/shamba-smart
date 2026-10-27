import { IconAlert, IconCheck } from '../icons'

export type Severity = 'info' | 'watch' | 'urgent'

const presentation = {
  info: { icon: IconCheck, label: 'Info' },
  watch: { icon: IconAlert, label: 'Watch' },
  urgent: { icon: IconAlert, label: 'Urgent' },
}

export function SeverityPill({ severity, label }: { severity: Severity; label?: string }) {
  const { icon: Icon, label: defaultLabel } = presentation[severity]
  return (
    <span className={`severity-pill severity-${severity}`}>
      <Icon size={14} aria-hidden />
      {label ?? defaultLabel}
    </span>
  )
}
