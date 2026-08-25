import enUS from './en-US.json'
import zhCN from './zh-CN.json'

export const localeStorageKey = 'rag-eval-webui.locale'
export const locales = ['zh-CN', 'en-US'] as const
export type Locale = typeof locales[number]
export type MessageKey = keyof typeof enUS
export type MessageValues = Record<string, string | number>

export const messages: Record<Locale, Record<MessageKey, string>> = {
  'en-US': enUS,
  'zh-CN': zhCN,
}

export function resolveLocale(savedLocale?: string | null, browserLocales: readonly string[] = []): Locale {
  if (savedLocale && locales.includes(savedLocale as Locale)) return savedLocale as Locale
  return browserLocales.some((locale) => locale.toLowerCase().startsWith('zh')) ? 'zh-CN' : 'en-US'
}

export function translate(locale: Locale, key: MessageKey, values: MessageValues = {}): string {
  return messages[locale][key].replace(/{{(\w+)}}/g, (_, token: string) => String(values[token] ?? `{{${token}}}`))
}

export function localizeEnumKey(value: string): MessageKey | null {
  const key = `status.${value.toLowerCase()}` as MessageKey
  return key in messages['en-US'] ? key : null
}

export function dictionaryKeys(locale: Locale): string[] {
  return Object.keys(messages[locale]).sort()
}
