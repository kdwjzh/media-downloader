// The queue as the backend reports it (contract section 4). Only events change it; the
// one getQueue() at start fills in what happened before the page listened.

import { create } from 'zustand'
import * as api from '../api'
import type { QueueItem, TaskProgress, TaskStatus } from '../types'
import { announce, showToast } from './notices'

export const FINISHED: ReadonlySet<TaskStatus> = new Set(['done', 'failed', 'cancelled'])

interface QueueState {
  items: QueueItem[]
  /** False until getQueue() answers. */
  loaded: boolean
}

export const useQueue = create<QueueState>(() => ({ items: [], loaded: false }))

// Ids events reported or removed before getQueue() answered: the events are newer
// news for them than a reply that may have been built earlier.
const seenEarly = new Set<string>()

export function resetQueue(): void {
  seenEarly.clear()
  useQueue.setState({ items: [], loaded: false })
}

export function loadQueue(snapshot: QueueItem[]): void {
  useQueue.setState((s) => ({
    items: [...snapshot.filter((item) => !seenEarly.has(item.id)), ...s.items],
    loaded: true,
  }))
  seenEarly.clear()
}

/** Known ids are replaced where they stand; new ones go to the bottom. A whole item each
 *  time, so a late or lost event is put right by the next one. */
export function tasksChanged(tasks: QueueItem[]): void {
  const { items, loaded } = useQueue.getState()
  const byId = new Map(tasks.map((task) => [task.id, task]))
  // A Map, not items.find(): one event can carry thousands of tasks (the bridge merges them).
  const known = new Map(items.map((item) => [item.id, item]))
  for (const task of tasks) {
    if (!loaded) seenEarly.add(task.id)
    const before = known.get(task.id)
    if (before && before.status !== task.status) speak(task)
  }
  useQueue.setState({
    items: [...items.map((item) => byId.get(item.id) ?? item), ...tasks.filter((task) => !known.has(task.id))],
  })
}

export function tasksRemoved(ids: string[]): void {
  const gone = new Set(ids)
  if (!useQueue.getState().loaded) for (const id of ids) seenEarly.add(id)
  useQueue.setState((s) => ({ items: s.items.filter((item) => !gone.has(item.id)) }))
}

/** All five progress fields are replaced: one the event leaves out has no value now. */
export function taskProgress({ id, percent, doneBytes, totalBytes, speedBps, etaSec }: TaskProgress): void {
  useQueue.setState((s) => ({
    items: s.items.map((item) =>
      item.id === id && item.status === 'downloading'
        ? { ...item, percent, doneBytes, totalBytes, speedBps, etaSec }
        : item,
    ),
  }))
}

// Only what people did not just do themselves, and nothing per percent (design step 9).
function speak(task: QueueItem): void {
  const title = task.title ?? task.url
  if (task.status === 'done') announce(task.skipped ? 'live.skipped' : 'live.done', { title })
  if (task.status === 'failed') announce('live.failed', { title, reason: `error.${task.error ?? 'unknown'}.title` })
  if (task.status === 'retrying') announce('live.retrying', { title })
}

// ---- what the rows' buttons do

export const cancel = (id: string) => api.cancelTask(id)
export const retry = (id: string) => api.retryTask(id)
export const addAgain = (id: string) => api.readdTask(id)
export const openLog = () => api.openLogFile()

/** Every unfinished task, one cancel_task each (decided in 4c: no command of its own).
 *  The calls go out together: one after another took ~0.1 s each in the real window, 9.8 s
 *  for 93. The waiting ones go first, so none gets a free slot and starts while the
 *  running ones stop. */
export async function cancelAll(): Promise<void> {
  const unfinished = useQueue.getState().items.filter((item) => !FINISHED.has(item.status))
  const cancelEach = (items: QueueItem[]) => Promise.all(items.map((item) => api.cancelTask(item.id)))
  await cancelEach(unfinished.filter((item) => item.status === 'queued'))
  await cancelEach(unfinished.filter((item) => item.status !== 'queued'))
}

export async function remove(id: string): Promise<void> {
  if ((await api.removeTask(id)).ok) announce('live.removed', { count: 1 })
}

export async function clearFinished(): Promise<void> {
  const count = useQueue.getState().items.filter((item) => FINISHED.has(item.status)).length
  if ((await api.clearFinished()).ok) announce('live.removed', { count })
}

export async function openFolder(id: string): Promise<void> {
  const reply = await api.openTaskFolder(id)
  const opened = reply.ok ? reply.data.opened : 'none'
  // Explorer showing the file is its own answer; the other two need a word.
  if (opened === 'folder') showToast('toast.openedFolder')
  if (opened === 'none') showToast('toast.notFound')
}
