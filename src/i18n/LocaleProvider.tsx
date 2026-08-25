import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { localeStorageKey, resolveLocale, translate, type Locale, type MessageKey, type MessageValues } from './index'

interface LocaleContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey, values?: MessageValues) => string
  formatDate: (value: string | number | Date) => string
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string
  formatPercent: (value: number, maximumFractionDigits?: number) => string
}

const LocaleContext = createContext<LocaleContextValue | null>(null)

function browserLocales(): string[] {
  if (typeof navigator === 'undefined') return []
  return navigator.languages?.length ? [...navigator.languages] : [navigator.language]
}

function savedLocale(): string | null {
  try { return window.localStorage.getItem(localeStorageKey) } catch { return null }
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => resolveLocale(savedLocale(), browserLocales()))
  const setLocale = (nextLocale: Locale) => setLocaleState(nextLocale)

  useEffect(() => {
    try { window.localStorage.setItem(localeStorageKey, locale) } catch { /* Storage can be unavailable in private contexts. */ }
    document.documentElement.lang = locale
    document.title = translate(locale, 'app.title')
  }, [locale])

  const value = useMemo<LocaleContextValue>(() => ({
    locale,
    setLocale,
    t: (key, values) => translate(locale, key, values),
    formatDate: (date) => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(date)),
    formatNumber: (number, options) => new Intl.NumberFormat(locale, options).format(number),
    formatPercent: (number, maximumFractionDigits = 0) => new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits }).format(number),
  }), [locale])

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useLocale(): LocaleContextValue {
  const context = useContext(LocaleContext)
  if (!context) throw new Error('useLocale must be used inside LocaleProvider')
  return context
}
