// The history screen's list. Loaded once, the first time the screen shows; after that only
// historyAdded and the screen's own deletes change it (decisions/0015).

import { create } from 'zustand'
import * as api from '../api'
import type { HistoryEntry } from '../types'
import { announce, showOpened, showToast } from './notices'

interface HistoryState {
  entries: HistoryEntry[]
  status: 'idle' | 'loading' | 'loaded' | 'failed'
  /** Entries whose "Download again" was pressed while the app has been open. */
  added: ReadonlySet<string>
}

export const useHistory = create<HistoryState>(() => ({ entries: [], status: 'idle', added: new Set() }))

// Entries added while listHistory() was on its way, newest first: the reply may or may not
// have them already.
let early: HistoryEntry[] = []

export function resetHistory(): void {
  early = []
  useHistory.setState({ entries: [], status: 'idle', added: new Set() })
}

export async function loadHistory(): Promise<void> {
  const { status } = useHistory.getState()
  if (status === 'loading' || status === 'loaded') return
  early = []
  useHistory.setState({ status: 'loading' })
  const reply = await api.listHistory()
  if (!reply.ok) {
    useHistory.setState({ status: 'failed' })
    return
  }
  const known = new Set(reply.data.map((entry) => entry.id))
  useHistory.setState({ entries: [...early.filter((entry) => !known.has(entry.id)), ...reply.data], status: 'loaded' })
  early = []
}

/** Newest on top. Before the first load there is no list yet: that load will bring it. */
export function historyAdded(entry: HistoryEntry): void {
  const { status } = useHistory.getState()
  if (status === 'loading') early = [entry, ...early]
  if (status !== 'loaded') return
  useHistory.setState((s) => ({ entries: [entry, ...s.entries.filter((e) => e.id !== entry.id)] }))
}

const without = (id: string) => useHistory.getState().entries.filter((entry) => entry.id !== id)

export async function downloadAgain(entry: HistoryEntry): Promise<void> {
  const reply = await api.redownloadHistory(entry.id)
  if (!reply.ok) return showToast('history.notAdded')
  if (!reply.data.taskId) {
    useHistory.setState({ entries: without(entry.id) })
    return showToast('history.gone')
  }
  useHistory.setState((s) => ({ added: new Set(s.added).add(entry.id) }))
  announce('live.added', { title: entry.title })
}

export async function openFolder(id: string): Promise<void> {
  const reply = await api.openHistoryFolder(id)
  showOpened(reply.ok ? reply.data.opened : 'none')
}

/** True when it is gone from the list. */
export async function deleteEntry(entry: HistoryEntry): Promise<boolean> {
  if (!(await api.deleteHistory(entry.id)).ok) return false
  useHistory.setState({ entries: without(entry.id) })
  announce('history.deleted', { title: entry.title })
  return true
}

export async function clearHistory(): Promise<void> {
  if ((await api.clearHistory()).ok) useHistory.setState({ entries: [] })
}
