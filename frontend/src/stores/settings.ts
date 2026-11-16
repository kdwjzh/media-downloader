import { create } from 'zustand'
import i18n, { systemLanguage } from '../i18n'
import type { Settings } from '../types'

/** Undefined until getSettings() answers. */
export const useSettings = create<{ settings?: Settings }>(() => ({}))

export function setSettings(settings: Settings): void {
  useSettings.setState({ settings })
  // shortcut: the language is applied here, but only 4e's settings page can change it.
  const lng = settings.language === 'system' ? systemLanguage() : settings.language
  if (i18n.language !== lng) void i18n.changeLanguage(lng)
}

