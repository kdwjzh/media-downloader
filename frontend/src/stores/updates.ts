// A newer app (for the nav dot and the settings page), the versions on the About section,
// and updating yt-dlp (decisions/0016).

import { create } from 'zustand'
import * as api from '../api'
import type { AboutInfo, ErrorCode } from '../types'

export type EngineCheck =
  | { state: 'idle' | 'checking' }
  | { state: 'latest' | 'updated'; version: string }
  | { state: 'failed'; code: ErrorCode }

interface UpdatesState {
  /** Only when newer than this app. Not found (offline, private repo) is the same as none. */
  latestVersion?: string
  about?: AboutInfo
  aboutStatus: 'idle' | 'loading' | 'loaded' | 'failed'
  engine: EngineCheck
}

const INITIAL: UpdatesState = { aboutStatus: 'idle', engine: { state: 'idle' } }

export const useUpdates = create<UpdatesState>(() => INITIAL)

export function resetUpdates(): void {
  useUpdates.setState(INITIAL, true)
}

/** Once at start (contract 3.5). The dot stays as long as a newer version exists. */
export async function checkAppUpdate(): Promise<void> {
  const reply = await api.checkAppUpdate()
  if (reply.ok) useUpdates.setState({ latestVersion: reply.data.latestVersion })
}

/** The first time the settings page shows: reading the versions starts three programs (~1.5 s). */
export async function loadAbout(force = false): Promise<void> {
  const { aboutStatus } = useUpdates.getState()
  if (!force && (aboutStatus === 'loading' || aboutStatus === 'loaded')) return
  useUpdates.setState({ aboutStatus: 'loading' })
  const reply = await api.getAbout()
  useUpdates.setState(reply.ok ? { about: reply.data, aboutStatus: 'loaded' } : { aboutStatus: 'failed' })
}

export async function updateEngine(): Promise<void> {
  if (useUpdates.getState().engine.state === 'checking') return
  useUpdates.setState({ engine: { state: 'checking' } })
  const reply = await api.updateEngine()
  if (!reply.ok) {
    useUpdates.setState({ engine: { state: 'failed', code: reply.error === 'network' ? 'network' : 'unknown' } })
    return
  }
  const { updated, version } = reply.data
  useUpdates.setState({ engine: { state: updated ? 'updated' : 'latest', version } })
  // The backend forgets its versions after an update; the About list asks again.
  if (updated) void loadAbout(true)
}

export const openLink = (target: 'releasePage' | 'sourceCode') => api.openLink(target)
export const openLogFolder = () => api.openLogFolder()
