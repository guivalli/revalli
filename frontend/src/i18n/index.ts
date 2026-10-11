import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import ptBR from './pt-BR.json'

export const LANGUAGES = { 'pt-BR': 'Português', en: 'English' } as const
const STORAGE_KEY = 'revalli.lang'

function initialLanguage(): string {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && saved in LANGUAGES) return saved
  } catch {
    /* armazenamento indisponível */
  }
  return navigator.language?.toLowerCase().startsWith('en') ? 'en' : 'pt-BR'
}

void i18n.use(initReactI18next).init({
  resources: { 'pt-BR': { translation: ptBR }, en: { translation: en } },
  lng: initialLanguage(),
  fallbackLng: 'pt-BR',
  interpolation: { escapeValue: false },
})

i18n.on('languageChanged', (lng) => {
  document.documentElement.lang = lng
  try {
    localStorage.setItem(STORAGE_KEY, lng)
  } catch {
    /* armazenamento indisponível */
  }
})

export default i18n
