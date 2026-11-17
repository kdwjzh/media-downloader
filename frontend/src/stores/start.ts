import { getQueue, getSettings, onEvent } from '../api'
import type { DataEvent } from '../api'
import { historyAdded } from './history'
import { previewSettingsChanged } from './preview'
import { loadQueue, taskProgress, tasksChanged, tasksRemoved } from './queue'
import { setSettings } from './settings'

export function handle(event: DataEvent): void {
  switch (event.type) {
    case 'tasksChanged':
      return tasksChanged(event.tasks)
    case 'tasksRemoved':
      return tasksRemoved(event.ids)
    case 'taskProgress':
      return taskProgress(event.progress)
    case 'settingsChanged':
      setSettings(event.settings)
      return previewSettingsChanged(event.settings)
    case 'historyAdded':
      return historyAdded(event.entry)
  }
}

/** Listens first, then asks: nothing that happens in between is missed (4a report, section 7). */
export function start(): () => void {
  const stop = onEvent(handle)
  void getQueue().then((reply) => reply.ok && loadQueue(reply.data))
  void getSettings().then((reply) => {
    if (!reply.ok) return
    setSettings(reply.data)
    previewSettingsChanged(reply.data)
  })
  return stop
}
