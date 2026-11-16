// api/ against a stand-in for pywebview's window.pywebview.api, and without one at all
// (a plain browser tab, where the stage 2 sample runs). No window, no Python.

import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { BackendEvent } from '../types'

type Api = typeof import('./index')
type Py = Record<string, ReturnType<typeof vi.fn>>

const OK = { ok: true }

/** A fresh copy of api/ in a fake window; `py` is what pywebview would have put there. */
async function load(py?: Py): Promise<{ api: Api; win: Record<string, unknown> }> {
  vi.resetModules()
  const listeners: Record<string, () => void> = {}
  const win: Record<string, unknown> = {
    pywebview: py ? { api: py } : undefined,
    addEventListener: (name: string, run: () => void) => (listeners[name] = run),
    fire: (name: string) => listeners[name]?.(),
  }
  vi.stubGlobal('window', win)
  return { api: await import('./index'), win }
}

function python(replies: Record<string, unknown> = {}): Py {
  const names = [
    'lookup', 'add_to_queue', 'get_queue', 'cancel_task', 'retry_task', 'readd_task',
    'remove_task', 'clear_finished', 'open_task_folder', 'list_history', 'redownload_history',
    'open_history_folder', 'delete_history', 'clear_history', 'get_settings', 'update_settings',
    'choose_download_folder', 'check_app_update', 'update_engine', 'get_about', 'open_log_file',
    'open_log_folder', 'open_link', 'confirm_close', 'ping',
  ]
  return Object.fromEntries(names.map((n) => [n, vi.fn(async () => replies[n] ?? OK)]))
}

function send(win: Record<string, unknown>, event: BackendEvent): void {
  ;(win.mediaDownloaderEvent as (e: BackendEvent) => void)(event)
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

// Each function: the command it calls, the arguments it passes on.
const CALLS: [keyof Api, unknown[], string][] = [
  ['lookup', ['https://youtu.be/x'], 'lookup'],
  ['addToQueue', [['u1', 'u2'], 'mp4', 1080], 'add_to_queue'],
  ['getQueue', [], 'get_queue'],
  ['cancelTask', ['t1'], 'cancel_task'],
  ['retryTask', ['t1'], 'retry_task'],
  ['readdTask', ['t1'], 'readd_task'],
  ['removeTask', ['t1'], 'remove_task'],
  ['clearFinished', [], 'clear_finished'],
  ['openTaskFolder', ['t1'], 'open_task_folder'],
  ['listHistory', [], 'list_history'],
  ['redownloadHistory', ['h1'], 'redownload_history'],
  ['openHistoryFolder', ['h1'], 'open_history_folder'],
  ['deleteHistory', ['h1'], 'delete_history'],
  ['clearHistory', [], 'clear_history'],
  ['getSettings', [], 'get_settings'],
  ['updateSettings', [{ maxConcurrent: 2 }], 'update_settings'],
  ['chooseDownloadFolder', [], 'choose_download_folder'],
  ['checkAppUpdate', [], 'check_app_update'],
  ['updateEngine', [], 'update_engine'],
  ['getAbout', [], 'get_about'],
  ['openLogFile', [], 'open_log_file'],
  ['openLogFolder', [], 'open_log_folder'],
  ['openLink', ['sourceCode'], 'open_link'],
  ['confirmClose', [], 'confirm_close'],
  ['ping', [], 'ping'],
]

test.each(CALLS)('%s calls %s with its arguments and hands back the reply', async (fn, args, command) => {
  const reply = { ok: true, data: { from: command } }
  const py = python({ [command]: reply })
  const { api } = await load(py)
  const run = api[fn] as (...a: unknown[]) => Promise<unknown>
  expect(await run(...args)).toEqual(reply)
  expect(py[command]).toHaveBeenCalledExactlyOnceWith(...args)
})

test('every command of the contract has a function', () => {
  expect(CALLS).toHaveLength(25)
})

test('a failure from the backend is passed on as it is', async () => {
  const { api } = await load(python({ lookup: { ok: false, error: 'private' } }))
  expect(await api.lookup('u')).toEqual({ ok: false, error: 'private' })
})

test('a call that throws or answers nonsense becomes unknown, never a rejection', async () => {
  const py = python({ get_queue: 'pong' })
  py.lookup.mockRejectedValue(new Error('TypeError in Python'))
  const { api } = await load(py)
  expect(await api.lookup('u')).toEqual({ ok: false, error: 'unknown' })
  expect(await api.getQueue()).toEqual({ ok: false, error: 'unknown' })
})

test('commands wait for pywebviewready', async () => {
  const py = python({ ping: { ok: true, data: 'pong' } })
  const { api, win } = await load()
  const reply = api.ping()
  win.pywebview = { api: py }
  ;(win.fire as (n: string) => void)('pywebviewready')
  expect(await reply).toEqual({ ok: true, data: 'pong' })
})

test('in a plain browser tab every command fails with unknown after the wait', async () => {
  const { api } = await load()
  const first = api.getSettings()
  await vi.advanceTimersByTimeAsync(5000)
  expect(await first).toEqual({ ok: false, error: 'unknown' })
  // From then on at once, no second wait.
  expect(await api.lookup('u')).toEqual({ ok: false, error: 'unknown' })
})

test('the half-made api pywebview puts there before it is ready is not used', async () => {
  const { api, win } = await load()
  win.pywebview = { api: {} }
  const reply = api.getQueue()
  win.pywebview = { api: python({ get_queue: { ok: true, data: [] } }) }
  ;(win.fire as (n: string) => void)('pywebviewready')
  expect(await reply).toEqual({ ok: true, data: [] })
})

test('events reach every listener until it unsubscribes', async () => {
  const { api, win } = await load(python())
  const a = vi.fn()
  const b = vi.fn()
  const stopA = api.onEvent(a)
  api.onEvent(b)
  const event: BackendEvent = { type: 'tasksRemoved', ids: ['t1'] }
  send(win, event)
  stopA()
  send(win, { type: 'tasksRemoved', ids: ['t2'] })
  expect(a).toHaveBeenCalledExactlyOnceWith(event)
  expect(b).toHaveBeenCalledTimes(2)
})

test('a listener that throws does not keep the event from the others', async () => {
  const { api, win } = await load(python())
  const error = vi.spyOn(console, 'error').mockImplementation(() => {})
  const after = vi.fn()
  api.onEvent(() => {
    throw new Error('a bug in a component')
  })
  api.onEvent(after)
  expect(() => send(win, { type: 'tasksRemoved', ids: [] })).not.toThrow()
  expect(after).toHaveBeenCalledOnce()
  expect(error).toHaveBeenCalledOnce()
})

test('closeRequested goes to its own handlers, not to onEvent', async () => {
  const py = python()
  const { api, win } = await load(py)
  const listener = vi.fn()
  const ask = vi.fn()
  api.onEvent(listener)
  api.onCloseRequested(ask)
  send(win, { type: 'closeRequested' })
  expect(ask).toHaveBeenCalledOnce()
  expect(listener).not.toHaveBeenCalled()
  expect(py.confirm_close).not.toHaveBeenCalled() // the handler decides
})

test('closeRequested with nobody to ask closes the window', async () => {
  const py = python()
  const { api, win } = await load(py)
  const stop = api.onCloseRequested(vi.fn())
  stop()
  send(win, { type: 'closeRequested' })
  await vi.waitFor(() => expect(py.confirm_close).toHaveBeenCalledOnce())
})
