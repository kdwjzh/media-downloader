// A newer app (for the nav dot and the settings page), updating the app (decisions/0019),
// the versions on the About section, and updating yt-dlp (decisions/0016).

import { create } from 'zustand'
import * as api from '../api'
import type { AboutInfo, AppUpdateStatus, ErrorCode } from '../types'
import { FINISHED, useQueue } from './queue'

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
  /** Where an update of the app is. */
  app: AppUpdateStatus
  /** Ask before installing: unfinished downloads would stop. */
  askInstall: boolean
}

const INITIAL: UpdatesState = { aboutStatus: 'idle', engine: { state: 'idle' }, app: { stage: 'idle' }, askInstall: false }

export const useUpdates = create<UpdatesState>(() => INITIAL)

export function resetUpdates(): void {
  useUpdates.setState(INITIAL, true)
}

/** Once at start (contract 3.5). The dot stays as long as a newer version exists. */
export async function checkAppUpdate(): Promise<void> {
  const reply = await api.checkAppUpdate()
  if (reply.ok) useUpdates.setState({ latestVersion: reply.data.latestVersion, app: reply.data.status ?? { stage: 'idle' } })
}

const unfinishedCount = () => useQueue.getState().items.filter((item) => !FINISHED.has(item.status)).length

/** "Update now" and "Retry": download and check; installing follows when it is ready. */
export async function startAppUpdate(): Promise<void> {
  const reply = await api.startAppUpdate()
  if (reply.ok) appUpdateChanged(reply.data, false)
}

export const cancelAppUpdate = () => api.cancelAppUpdate()

/** Installs at once when nothing is downloading; otherwise asks first (decisions/0019). */
export function installAppUpdate(): void {
  if (unfinishedCount() > 0) useUpdates.setState({ askInstall: true })
  else void confirmInstall()
}

export async function confirmInstall(): Promise<void> {
  useUpdates.setState({ askInstall: false })
  const reply = await api.installAppUpdate()
  // A refused installer comes back as a failed status event; this covers a reply without one.
  if (!reply.ok && useUpdates.getState().app.stage !== 'failed') {
    useUpdates.setState({ app: { stage: 'failed', error: reply.error } })
  }
}

export const keepDownloading = () => useUpdates.setState({ askInstall: false })

/** The event: becoming ready installs (or asks) right away, since the user asked for it. */
export function appUpdateChanged(status: AppUpdateStatus, fromEvent = true): void {
  const was = useUpdates.getState().app.stage
  useUpdates.setState({ app: status })
  if (fromEvent && status.stage === 'ready' && was !== 'ready') installAppUpdate()
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
