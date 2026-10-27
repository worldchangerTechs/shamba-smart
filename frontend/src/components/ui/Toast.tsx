import { IconCheck, IconClose } from '../icons'

export function Toast({ message, tone, onDismiss }: {
  message: string
  tone: 'success' | 'error'
  onDismiss: () => void
}) {
  const Icon = tone === 'success' ? IconCheck : IconClose
  return (
    <div className={`toast toast-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon size={19} aria-hidden />
      <p className="flex-1 text-sm font-medium">{message}</p>
      <button className="icon-button -mr-2" onClick={onDismiss} aria-label="Dismiss message">
        <IconClose size={17} aria-hidden />
      </button>
    </div>
  )
}
