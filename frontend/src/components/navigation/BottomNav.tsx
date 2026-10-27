import { IconAlert as Bell, IconLearn as BookOpen, IconEllipsis as Ellipsis, IconHome as House, IconSprout as Sprout, IconStore as Store, IconClose as X } from '../icons'
import { NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { useI18n } from '../../i18n/I18nProvider'
import { useAuth } from '../../auth/AuthProvider'

const items = [
  { to: '/app', label: 'home' as const, icon: House },
  { to: '/app/farms', label: 'farms' as const, icon: Sprout },
  { to: '/app/alerts', label: 'alerts' as const, icon: Bell },
  { to: '/app/market', label: 'market' as const, icon: Store },
  { to: '/app/learn', label: 'learn' as const, icon: BookOpen },
]

export function BottomNav() {
  const { t } = useI18n()
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)
  if (user?.role === 'OFFICER' || user?.role === 'ADMIN') return null
  const extraItems = [
    { to: '/app/planner', label: 'planner' as const },
    { to: '/app/soil', label: 'soilDoctor' as const },
    { to: '/app/spray-safe', label: 'spraySafe' as const },
    { to: '/app/erosion', label: 'erosionGuard' as const },
    { to: '/app/pests', label: 'pestRadar' as const },
    { to: '/app/waste', label: 'wasteLoop' as const },
    { to: '/app/alerts', label: 'alerts' as const },
  ]
  return (
    <>
    {moreOpen && <button className="mobile-more-scrim" aria-label="Close more navigation" onClick={() => setMoreOpen(false)} />}
    {moreOpen && <div className="mobile-more-menu">
      <div className="mobile-more-head"><strong>{t('allTools')}</strong><button className="icon-button" onClick={() => setMoreOpen(false)} aria-label="Close"><X size={18} /></button></div>
      <div className="mobile-more-grid">{extraItems.map(({ to, label }) => <NavLink key={to} to={to} onClick={() => setMoreOpen(false)} className={({ isActive }) => `mobile-more-link ${isActive ? 'is-active' : ''}`}>{t(label)}</NavLink>)}</div>
    </div>}
    <nav className="bottom-nav" aria-label="Main navigation">
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === '/app'} className={({ isActive }) => `bottom-nav-link ${isActive ? 'is-active' : ''}`}>
          <Icon size={21} aria-hidden />
          <span>{t(label)}</span>
        </NavLink>
      ))}
      <button className={`bottom-nav-link ${extraItems.some((item) => item.to === pathname) ? 'is-active' : ''}`} aria-expanded={moreOpen} onClick={() => setMoreOpen((open) => !open)}>
        <Ellipsis size={21} /><span>{t('more')}</span>
      </button>
    </nav>
    </>
  )
}
