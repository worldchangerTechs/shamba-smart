import { useI18n } from '../../i18n/I18nProvider'

const options = [
  { value: 'en', label: 'EN' },
  { value: 'sw', label: 'KISW' },
  { value: 'guz', label: 'EKEGUSII' },
] as const

export function LanguageSwitcher() {
  const { language, setLanguage, t } = useI18n()
  return (
    <select
      aria-label={t('language')}
      className="language-switcher"
      value={language}
      onChange={(event) => setLanguage(event.target.value as 'en' | 'sw' | 'guz')}
    >
      {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  )
}
