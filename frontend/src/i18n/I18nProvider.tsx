import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'
import en from './en.json'
import sw from './sw.json'
import guz from './guz.json'
import type { Language } from '../types'

const dictionaries = { en, sw, guz }
type Dictionary = typeof en
interface I18nValue {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: keyof Dictionary) => string
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: PropsWithChildren) {
  const [language, setLanguage] = useState<Language>(() => {
    const stored = localStorage.getItem('shamba_language')
    return stored === 'sw' || stored === 'guz' ? stored : 'en'
  })
  useEffect(() => {
    document.documentElement.lang = language
  }, [language])
  const changeLanguage = useCallback((value: Language) => {
    localStorage.setItem('shamba_language', value)
    setLanguage(value)
  }, [])
  const t = useCallback((key: keyof Dictionary) =>
    dictionaries[language][key] || dictionaries.en[key] || key, [language])
  const value = useMemo(() => ({ language, setLanguage: changeLanguage, t }), [language, changeLanguage, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used within I18nProvider')
  return context
}
