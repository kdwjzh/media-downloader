// The only place in the frontend that talks to pywebview. Everything else goes through
// ./index.ts, which knows the commands; this file only knows how to reach Python.

import type { BackendEvent, ErrorCode } from '../types'

/** Every command answers like this (contract 1.1). A failure is a value, never a throw. */
export type Reply<T> = { ok: true; data: T } | { ok: false; error: ErrorCode }

type PyApi = Record<string, (...args: unknown[]) => Promise<unknown>>

declare global {
  interface Window {
    pywebview?: { api?: PyApi }
    // backend/app/bridge/events.py calls it; keep the two names the same.
    mediaDownloaderEvent?: (event: BackendEvent) => void
  }
}

const READY_TIMEOUT_MS = 5000
const NO_BACKEND: Reply<never> = { ok: false, error: 'unknown' }

// pywebview creates window.pywebview.api empty and fills it before 'pywebviewready'.
function loaded(): PyApi | undefined {
  const api = typeof window === 'undefined' ? undefined : window.pywebview?.api
  return typeof api?.ping === 'function' ? api : undefined
}

let waiting: Promise<PyApi | undefined> | undefined

function bridge(): Promise<PyApi | undefined> {
  const api = loaded()
  if (api) return Promise.resolve(api)
  if (typeof window === 'undefined') return Promise.resolve(undefined)
  // In a plain browser tab (the stage 2 sample, `npm run dev` alone) the event never comes:
  // give up once, and from then on every command fails at once instead of waiting again.
  waiting ??= new Promise((resolve) => {
    const timer = setTimeout(() => resolve(undefined), READY_TIMEOUT_MS)
    window.addEventListener(
      'pywebviewready',
      () => {
        clearTimeout(timer)
        resolve(loaded())
      },
      { once: true },
    )
  })
  return waiting
}

function isReply(value: unknown): value is Reply<unknown> {
  return typeof value === 'object' && value !== null && typeof (value as { ok?: unknown }).ok === 'boolean'
}

/** Calls one backend command. Without a backend, or when anything breaks on the way, the
 *  reply is { ok: false, error: 'unknown' }. */
export async function invoke<T>(command: string, ...args: unknown[]): Promise<Reply<T>> {
  const api = await bridge()
  const method = api?.[command]
  if (typeof method !== 'function') return NO_BACKEND
  try {
    const reply = await method(...args)
    return isReply(reply) ? (reply as Reply<T>) : NO_BACKEND
  } catch {
    return NO_BACKEND
  }
}

/** Installs the one receiver the backend calls with every event. */
export function receiveEvents(receiver: (event: BackendEvent) => void): void {
  if (typeof window !== 'undefined') window.mediaDownloaderEvent = receiver
}
