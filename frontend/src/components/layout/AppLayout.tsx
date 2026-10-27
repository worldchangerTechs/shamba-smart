import { IconAlert as Bell, IconLogOut as LogOut, IconSprout as Sprout } from '../icons'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../auth/AuthProvider'
import { useI18n } from '../../i18n/I18nProvider'
import { BottomNav } from '../navigation/BottomNav'
import { Sidebar } from '../navigation/Sidebar'
import { LanguageSwitcher } from '../ui/LanguageSwitcher'
import { useOfflineStatus } from '../../hooks/useOfflineStatus'

function OfflineStatus() {
  const { online, pendingCount, failedCount, lastUpdated } = useOfflineStatus()
  return (
    <div className="offline-status" aria-live="polite">
      {!online && <span className="offline-status-badge"><span /> Offline</span>}
      {pendingCount > 0 && <span className="offline-queue-badge">{pendingCount} queued</span>}
      {failedCount > 0 && <span className="offline-failed-badge">{failedCount} need review</span>}
      <span className="offline-last-updated" title={lastUpdated ? new Date(lastUpdated).toLocaleString() : 'No cached content yet'}>
        {lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Not synced'}
      </span>
    </div>
  )
}

export function AppLayout() {
  const { user, signOut } = useAuth()
  const { t, language } = useI18n()
  const location = useLocation()
  const initials = `${user?.first_name?.[0] ?? ''}${user?.last_name?.[0] ?? ''}` || 'F'
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <header className="topbar">
          <Link to="/app" className="brand-lockup mobile-brand">
            <span className="brand-mark"><Sprout size={21} aria-hidden /></span>
            <span className="font-display text-xl font-bold">Shamba</span>
          </Link>
          <div className="topbar-tools">
            <OfflineStatus />
            <div className="language-control">
              <LanguageSwitcher />
              {language === 'guz' && <span className="language-review-note">Review needed</span>}
            </div>
            {user?.role === 'FARMER' && <Link to="/app/alerts" className="icon-button notification-button" aria-label={t('alerts')}>
              <Bell size={20} aria-hidden />
              <span className="notification-dot" />
            </Link>}
            <div className="avatar" title={user?.phone}>{initials}</div>
            <button onClick={signOut} className="icon-button mobile-signout" aria-label={t('logout')}>
              <LogOut size={19} aria-hidden />
            </button>
          </div>
        </header>
        <main key={location.pathname} className="page-content">
          <Outlet />
        </main>
        <BottomNav />
      </div>
    </div>
  )
}
