import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import zhTW from './zh-TW.json'

export function systemLanguage(): 'zh-TW' | 'en' {
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh-TW' : 'en'
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, 'zh-TW': { translation: zhTW } },
  lng: systemLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

// Screen readers and CJK glyph selection both depend on <html lang>.
i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng
})
document.documentElement.lang = i18n.language

export default i18n
