import { IconAlert as Bell, IconLearn as BookOpen, IconCloudRain as CloudRain, IconFlask as FlaskConical, IconHome as House, IconLogOut as LogOut, IconShieldCheck as ShieldCheck, IconSprout as Sprout, IconStore as Store, IconWaves as Waves, IconPest as Bug, IconWaste as Recycle } from '../icons'
import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../../auth/AuthProvider'
import { useI18n } from '../../i18n/I18nProvider'

const items = [
  { to: '/app', label: 'home' as const, icon: House },
  { to: '/app/farms', label: 'farms' as const, icon: Sprout },
  { to: '/app/planner', label: 'planner' as const, icon: CloudRain },
  { to: '/app/soil', label: 'soilDoctor' as const, icon: FlaskConical },
  { to: '/app/spray-safe', label: 'spraySafe' as const, icon: ShieldCheck },
  { to: '/app/erosion', label: 'erosionGuard' as const, icon: Waves },
  { to: '/app/pests', label: 'pestRadar' as const, icon: Bug },
  { to: '/app/market', label: 'market' as const, icon: Store },
  { to: '/app/learn', label: 'learn' as const, icon: BookOpen },
  { to: '/app/waste', label: 'wasteLoop' as const, icon: Recycle },
  { to: '/app/alerts', label: 'alerts' as const, icon: Bell },
]

export function Sidebar() {
  const { t } = useI18n()
  const { signOut, user } = useAuth()
  if (user?.role === 'OFFICER' || user?.role === 'ADMIN') {
    return (
      <aside className="sidebar">
        <Link to="/app" className="brand-lockup">
          <span className="brand-mark"><Sprout size={23} aria-hidden /></span>
          <span className="font-display text-2xl font-bold tracking-tight">Shamba</span>
        </Link>
        <nav className="mt-10 space-y-1" aria-label="Main navigation">
          <NavLink to="/app" end className={({ isActive }) => `sidebar-link ${isActive ? 'is-active' : ''}`}>
            {user.role === 'OFFICER' ? <ShieldCheck size={19} aria-hidden /> : <House size={19} aria-hidden />}
            <span>{user.role === 'OFFICER' ? 'Ward operations' : 'County dashboard'}</span>
          </NavLink>
        </nav>
        <button onClick={signOut} className="sidebar-link mt-auto text-soil/60">
          <LogOut size={19} aria-hidden /><span>{t('logout')}</span>
        </button>
      </aside>
    )
  }
  return (
    <aside className="sidebar">
      <Link to="/app" className="brand-lockup">
        <span className="brand-mark"><Sprout size={23} aria-hidden /></span>
        <span className="font-display text-2xl font-bold tracking-tight">Shamba</span>
      </Link>
      <nav className="mt-10 space-y-1" aria-label="Main navigation">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === '/app'} className={({ isActive }) => `sidebar-link ${isActive ? 'is-active' : ''}`}>
            <Icon size={19} aria-hidden />
            <span>{t(label)}</span>
          </NavLink>
        ))}
      </nav>
      <button onClick={signOut} className="sidebar-link mt-auto text-soil/60">
        <LogOut size={19} aria-hidden /><span>{t('logout')}</span>
      </button>
    </aside>
  )
}
