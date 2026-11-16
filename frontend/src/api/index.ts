// The backend's commands and events (docs/介面與後端的約定.md), one typed function each.
// Components import from here; none of them knows a command name or pywebview.

import type {
  AboutInfo,
  AppUpdateInfo,
  BackendEvent,
  EngineUpdateResult,
  Format,
  HistoryEntry,
  LookupResult,
  OpenResult,
  QueueItem,
  Settings,
  SettingsChanges,
} from '../types'
import { type Reply, invoke, receiveEvents } from './bridge'

export type { Reply } from './bridge'

/** Every command: its arguments and what `data` holds when it works (void: no data).
 *  backend/tests/test_types_ts.py checks these names against the Python bridge. */
export interface Commands {
  lookup(url: string): LookupResult
  add_to_queue(urls: string[], format: Format, quality: number): { taskIds: string[] }
  get_queue(): QueueItem[]
  cancel_task(id: string): void
  retry_task(id: string): void
  readd_task(id: string): void
  remove_task(id: string): void
  clear_finished(): void
  open_task_folder(id: string): OpenResult
  list_history(): HistoryEntry[]
  redownload_history(id: string): { taskId?: string }
  open_history_folder(id: string): OpenResult
  delete_history(id: string): void
  clear_history(): void
  get_settings(): Settings
  update_settings(changes: SettingsChanges): Settings
  choose_download_folder(): Settings
  check_app_update(): AppUpdateInfo
  update_engine(): EngineUpdateResult
  get_about(): AboutInfo
  open_log_file(): void
  open_log_folder(): void
  open_link(target: 'releasePage' | 'sourceCode'): void
  confirm_close(): void
  ping(): string
}

type Command = keyof Commands

function call<K extends Command>(
  command: K,
  ...args: Parameters<Commands[K]>
): Promise<Reply<ReturnType<Commands[K]>>> {
  return invoke(command, ...args)
}

export const lookup = (url: string) => call('lookup', url)
export const addToQueue = (urls: string[], format: Format, quality: number) =>
  call('add_to_queue', urls, format, quality)
export const getQueue = () => call('get_queue')
export const cancelTask = (id: string) => call('cancel_task', id)
export const retryTask = (id: string) => call('retry_task', id)
export const readdTask = (id: string) => call('readd_task', id)
export const removeTask = (id: string) => call('remove_task', id)
export const clearFinished = () => call('clear_finished')
export const openTaskFolder = (id: string) => call('open_task_folder', id)
export const listHistory = () => call('list_history')
export const redownloadHistory = (id: string) => call('redownload_history', id)
export const openHistoryFolder = (id: string) => call('open_history_folder', id)
export const deleteHistory = (id: string) => call('delete_history', id)
export const clearHistory = () => call('clear_history')
export const getSettings = () => call('get_settings')
export const updateSettings = (changes: SettingsChanges) => call('update_settings', changes)
/** Opens the system's folder dialog. A folder that cannot be written to fails: show the
 *  dedicated message, not the generic unknown error (contract 3.4). */
export const chooseDownloadFolder = () => call('choose_download_folder')
export const checkAppUpdate = () => call('check_app_update')
export const updateEngine = () => call('update_engine')
export const getAbout = () => call('get_about')
export const openLogFile = () => call('open_log_file')
export const openLogFolder = () => call('open_log_folder')
export const openLink = (target: 'releasePage' | 'sourceCode') => call('open_link', target)
/** After closeRequested, when the user agrees: stops every download and closes the window. */
export const confirmClose = () => call('confirm_close')
export const ping = () => call('ping')

// ---- events (contract section 4)

export type DataEvent = Exclude<BackendEvent, { type: 'closeRequested' }>

const listeners = new Set<(event: DataEvent) => void>()
const closeHandlers = new Set<() => void>()

/** Every event but closeRequested. Returns the function that unsubscribes. */
export function onEvent(listener: (event: DataEvent) => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The window's close button was pressed while tasks still run. The handler asks the user
 *  and calls confirmClose() to close. With no handler at all the window simply closes. */
export function onCloseRequested(handler: () => void): () => void {
  closeHandlers.add(handler)
  return () => closeHandlers.delete(handler)
}

function deliver(event: BackendEvent): void {
  if (event.type === 'closeRequested') {
    if (closeHandlers.size === 0) void confirmClose()
    for (const handler of [...closeHandlers]) safely(handler)
    return
  }
  for (const listener of [...listeners]) safely(() => listener(event))
}

// One listener that throws must not keep the event from the others, nor reach the backend.
function safely(run: () => void): void {
  try {
    run()
  } catch (error) {
    console.error(error)
  }
}

receiveEvents(deliver)
