import { create } from 'zustand'
import * as api from '../api'
import i18n, { systemLanguage } from '../i18n'
import type { Settings, SettingsChanges } from '../types'
import { showToast } from './notices'
import { FINISHED, useQueue } from './queue'

/** Undefined until getSettings() answers. */
export const useSettings = create<{ settings?: Settings; folderFailed: boolean }>(() => ({ folderFailed: false }))

export function setSettings(settings: Settings): void {
  useSettings.setState({ settings })
  const lng = settings.language === 'system' ? systemLanguage() : settings.language
  if (i18n.language !== lng) void i18n.changeLanguage(lng)
}

/** Shown at once; the reply (and settingsChanged) brings the backend's own copy. A failure
 *  puts the controls back to what the backend has (decisions/0016). */
export async function changeSettings(changes: SettingsChanges): Promise<void> {
  const current = useSettings.getState().settings
  if (current) setSettings({ ...current, ...changes })
  const reply = await api.updateSettings(changes)
  if (reply.ok) return setSettings(reply.data)
  const fresh = await api.getSettings()
  if (fresh.ok) setSettings(fresh.data)
}

/** The system's folder dialog. Any failure is the folder that cannot be written to (contract
 *  3.4); the message stays until the next try. */
export async function chooseFolder(): Promise<void> {
  const before = useSettings.getState().settings?.downloadDir
  useSettings.setState({ folderFailed: false })
  const reply = await api.chooseDownloadFolder()
  if (!reply.ok) return useSettings.setState({ folderFailed: true })
  setSettings(reply.data)
  if (reply.data.downloadDir === before) return
  // Items already queued keep the folder they were added with (contract 3.4).
  const unfinished = useQueue.getState().items.filter((item) => !FINISHED.has(item.status)).length
  if (unfinished > 0) showToast('settings.keptOldFolder', { count: unfinished })
}
