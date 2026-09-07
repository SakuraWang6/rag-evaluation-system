import { describe, expect, it } from 'vitest'
import { dictionaryKeys, locales, resolveLocale, translate } from './index'

describe('i18n foundation', () => {
  it('keeps zh-CN and en-US dictionaries in exact key parity', () => {
    expect(dictionaryKeys('zh-CN')).toEqual(dictionaryKeys('en-US'))
  })

  it('prefers a saved locale, then maps zh browser locales to zh-CN', () => {
    expect(resolveLocale('en-US', ['zh-CN'])).toBe('en-US')
    expect(resolveLocale(null, ['zh-Hant-TW', 'en-US'])).toBe('zh-CN')
    expect(resolveLocale(null, ['fr-FR'])).toBe('en-US')
    expect(locales).toEqual(['zh-CN', 'en-US'])
  })

  it('keeps the compact dataset-creation labels available in both languages', () => {
    for (const locale of locales) {
      expect(translate(locale, 'product.datasets.createDataset')).not.toBe('')
      expect(translate(locale, 'product.datasets.authoringBlocked')).not.toBe('')
      expect(translate(locale, 'product.authoring.generateBatch', { count: 3 })).not.toBe('')
    }
  })
})
