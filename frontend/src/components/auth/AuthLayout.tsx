import { useEffect, useRef } from 'react'
import type { PropsWithChildren, ReactNode } from 'react'
import './auth.css'

export type AuthVariant = 'register' | 'login' | 'onboarding'

export function AuthLayout({ variant, children }: PropsWithChildren<{ variant: AuthVariant }>) {
  const isLogin = variant === 'login'
  const isOnboarding = variant === 'onboarding'
  const eyebrow = isLogin ? 'YOUR FARM. YOUR NEXT STEP.' : isOnboarding ? 'A BETTER FARM PLAN' : 'MADE FOR KISII FARMERS'

  return (
    <main className="auth-page">
      <div className="auth-backdrop" aria-hidden="true">
        <picture className="auth-background">
          <source srcSet="/images/register-leaves-800.webp 800w, /images/register-leaves-1600.webp 1600w" type="image/webp" />
          <img src="/images/register-leaves.jpg" alt="" />
        </picture>
        <picture className="auth-background auth-background-blur">
          <source srcSet="/images/register-leaves-800.webp 800w, /images/register-leaves-1600.webp 1600w" type="image/webp" />
          <img src="/images/register-leaves.jpg" alt="" />
        </picture>
      </div>
      <div className={`auth-frame auth-frame-${variant}`}>
        <section className="auth-story" aria-label="About Shamba Smart">
          <div className="auth-story-copy">
            <p className="auth-story-eyebrow">{eyebrow}</p>
            <h1 className="auth-headline" aria-label={isLogin ? 'Welcome back' : isOnboarding ? 'Your farm, your way' : "Let's get started"}>
              {isLogin ? <><span className="auth-word auth-word-first">Welcome</span> <span className="auth-word auth-word-accent">back</span></> :
                isOnboarding ? <><span className="auth-word auth-word-first">Your farm,</span> <span className="auth-word auth-word-accent">your way</span></> :
                  <><span className="auth-word auth-word-first">Let’s get</span> <span className="auth-word auth-word-accent">started</span></>}
            </h1>
            <p className="auth-story-description">
              {isLogin
                ? 'Sign in to see today’s warnings for your farm.'
                : isOnboarding
                  ? 'A few details help us make weather and crop advice more useful for your land.'
                  : 'Register your farm in two minutes. We send rain, pest and market warnings to your phone by app, SMS or voice, in English, Kiswahili or Ekegusii.'}
            </p>
          </div>
          <p className="auth-story-footnote">No smartphone? Dial *384# or ask your extension officer to register you.</p>
        </section>
        <section className="auth-panel" aria-label={isLogin ? 'Sign in' : isOnboarding ? 'Farm setup' : 'Create an account'}>
          {children}
        </section>
      </div>
    </main>
  )
}

export function AuthModal({ title, children, onClose }: PropsWithChildren<{ title: string; onClose: () => void }>) {
  const closeButton = useRef<HTMLButtonElement>(null)
  const modal = useRef<HTMLElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeButton.current?.focus()
    const handleKeys = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab' || !modal.current) return
      const focusable = Array.from(modal.current.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', handleKeys)
    return () => {
      window.removeEventListener('keydown', handleKeys)
      previousFocus?.focus()
    }
  }, [])

  return (
    <div className="auth-modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section ref={modal} className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
        <button ref={closeButton} type="button" className="auth-modal-close" onClick={onClose}>Close</button>
        <h2 id="auth-modal-title">{title}</h2>
        {children}
      </section>
    </div>
  )
}

export function AuthDivider() {
  return <div className="auth-divider" aria-hidden="true"><span>OR</span></div>
}

export function AuthNotice({ children }: { children: ReactNode }) {
  return <p className="auth-notice" aria-live="polite">{children}</p>
}
