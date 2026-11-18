// @vitest-environment jsdom
// The screen against a stand-in for pywebview: the real api/ and stores, a fake
// window.pywebview.api, events pushed through window.mediaDownloaderEvent. No Python.

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, expect, test, vi } from 'vitest'
import type { BackendEvent, MediaInfo, Preview, QueueItem } from '../types'

const COMMANDS = [
  'ping', 'lookup', 'add_to_queue', 'get_queue', 'get_settings', 'cancel_task', 'retry_task', 'readd_task',
  'remove_task', 'clear_finished', 'open_task_folder', 'open_log_file', 'confirm_close',
]
const py: Record<string, ReturnType<typeof vi.fn>> = Object.fromEntries(COMMANDS.map((name) => [name, vi.fn()]))
window.pywebview = { api: py as never }

// jsdom has no <dialog> behaviour; the app relies on the browser's.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
})

const i18n = (await import('../i18n')).default
const { default: App } = await import('../App')
const { QueueRow } = await import('./QueueRow')
const { PreviewPanel } = await import('./PreviewPanel')
const { ConfirmCloseDialog } = await import('./ConfirmCloseDialog')
const { ErrorBoundary } = await import('./ErrorBoundary')
const { usePreview, resetPreview } = await import('../stores/preview')
const { resetQueue, loadQueue } = await import('../stores/queue')
const { useNotices } = await import('../stores/notices')
const { handle } = await import('../stores/start')
const { onEvent } = await import('../api')
onEvent(handle)

/** Lets the api/ promises and the React updates after them run. */
const settle = () => act(() => new Promise<void>((r) => setTimeout(r, 0)))

const MB = 1024 * 1024
const item = (status: QueueItem['status'], more: Partial<QueueItem> = {}): QueueItem => ({
  id: 'a',
  url: 'https://youtu.be/a',
  title: 'A song',
  format: 'mp3',
  quality: 320,
  status,
  ...more,
})
const info: MediaInfo = {
  url: 'https://youtu.be/v',
  title: 'A video',
  channel: 'A channel',
  durationSec: 241,
  platform: 'youtube',
  thumb: 'https://i.ytimg.com/vi/v/hqdefault.jpg',
  options: [
    { format: 'mp3', quality: 128, sizeBytes: 3 * MB },
    { format: 'mp3', quality: 192, sizeBytes: 5 * MB },
    { format: 'mp3', quality: 320, sizeBytes: 9 * MB },
    { format: 'mp4', quality: 720 },
  ],
}

async function send(event: BackendEvent) {
  await act(async () => window.mediaDownloaderEvent?.(event))
  await settle()
}

function row(it: QueueItem) {
  return render(
    <ul>
      <QueueRow item={it} />
    </ul>,
  )
}

const text = () => document.body.textContent

beforeEach(async () => {
  for (const fn of Object.values(py)) fn.mockReset().mockResolvedValue({ ok: true })
  py.ping.mockResolvedValue({ ok: true, data: 'pong' })
  py.lookup.mockReturnValue(new Promise(() => {}))
  await i18n.changeLanguage('en')
  resetQueue()
  loadQueue([])
  resetPreview()
  useNotices.setState({ toast: undefined, spoken: [] })
})
afterEach(cleanup)

// ---- the nine statuses, and the three ways a download may look

test.each<[string, QueueItem, string, number | null | undefined]>([
  ['queued', item('queued'), 'Waiting', undefined],
  ['fetching', item('fetching', { title: undefined }), 'Looking up video info…', null],
  ['starting', item('downloading', { percent: 0, doneBytes: 0 }), 'Starting download…', null],
  ['with percent', item('downloading', { percent: 62, doneBytes: 599 * MB, totalBytes: 966 * MB, speedBps: 8.4 * MB, etaSec: 44 }), 'Downloading 62%599 MB / 966 MB8.4 MB/s0:44 left', 62],
  ['without total', item('downloading', { percent: 12, doneBytes: 118 * MB, speedBps: 2.1 * MB }), 'Downloading 12%118 MB2.1 MB/s', 12],
  ['without percent', item('downloading', { doneBytes: 118 * MB, speedBps: 2.1 * MB }), 'Downloading118 MB2.1 MB/s', null],
  ['retrying', item('retrying', { attempt: 2, percent: 40, doneBytes: 4 * MB }), 'Connection lost, retrying (attempt 2)', 40],
  ['converting', item('converting'), 'Converting', null],
  ['merging', item('merging', { format: 'mp4' }), 'Merging', null],
  ['done', item('done', { sizeBytes: 9 * MB }), 'Done9.0 MB', undefined],
  ['skipped', item('done', { skipped: true }), 'File already exists, skipped', undefined],
  ['failed', item('failed', { error: 'private' }), 'Download failed: This video is private.', undefined],
  ['cancelled', item('cancelled'), 'Cancelled', undefined],
])('a %s row', (_name, it, status, bar) => {
  row(it)
  expect(text()).toContain(status)
  const progress = screen.queryByRole('progressbar')
  // undefined: no bar; null: a sweeping bar with no number; a number: a filled bar.
  if (bar === undefined) expect(progress).toBeNull()
  else expect(progress?.getAttribute('aria-valuenow') ?? null).toBe(bar === null ? null : String(bar))
})

test('a fetching row shows the URL where the title will be', () => {
  row(item('fetching', { title: undefined }))
  expect(text()).toContain('https://youtu.be/a')
})

// ---- the preview's three states

function preview(p: Preview) {
  usePreview.setState({ preview: p })
  return render(<PreviewPanel onDone={() => {}} />)
}

test('a preview looking up', () => {
  preview({ kind: 'loading', url: 'https://youtu.be/v', started: Date.now() })
  expect(screen.getByRole('region').getAttribute('aria-busy')).toBe('true')
  expect(text()).toContain('Looking up video info…')
})

test('a lookup past five seconds counts the real seconds, outside the live status', () => {
  vi.useFakeTimers()
  try {
    preview({ kind: 'loading', url: 'https://youtu.be/v', started: Date.now() })
    act(() => vi.advanceTimersByTime(4000))
    expect(text()).not.toContain('Still looking')
    act(() => vi.advanceTimersByTime(8000))
    expect(text()).toContain('Still looking (12 s)')
    expect(screen.getByRole('status').textContent).toBe('Looking up video info…')
  } finally {
    vi.useRealTimers()
  }
})

test('a preview found, with the choice remembered and the real thumbnail', () => {
  preview({ kind: 'ready', info })
  expect(text()).toContain('A video')
  expect(text()).toContain('~9.0 MB')
  expect(document.querySelector('img')?.getAttribute('src')).toBe(info.thumb)
  fireEvent.click(screen.getByLabelText('MP4'))
  expect(text()).toContain('Size unknown')
})

test('a preview that failed', async () => {
  preview({ kind: 'error', url: 'https://youtu.be/v', code: 'network' })
  expect(screen.getByRole('alert').textContent).toContain("Can't connect")
  fireEvent.click(screen.getByText('Retry'))
  await settle()
  expect(py.lookup).toHaveBeenCalledWith('https://youtu.be/v')
})

// ---- every button reaches the right command

test.each<[string, QueueItem, string, string, unknown[]]>([
  ['Cancel', item('downloading', { percent: 1, doneBytes: 1 }), 'Cancel: A song', 'cancel_task', ['a']],
  ['Retry', item('failed', { error: 'network' }), 'Retry: A song', 'retry_task', ['a']],
  ['Add again', item('cancelled'), 'Add again: A song', 'readd_task', ['a']],
  ['Remove', item('done'), 'Remove from queue: A song', 'remove_task', ['a']],
  ['Open folder', item('done'), 'Open folder: A song', 'open_task_folder', ['a']],
  ['Open log', item('failed', { error: 'unknown' }), 'Open log file', 'open_log_file', []],
])('the row button %s', async (_name, it, label, command, args) => {
  py.open_task_folder.mockResolvedValue({ ok: true, data: { opened: 'file' } })
  row(it)
  await act(async () => fireEvent.click(screen.getByRole('button', { name: label })))
  await settle()
  expect(py[command]).toHaveBeenCalledWith(...args)
})

test('retry is not offered for an error retrying cannot fix', () => {
  row(item('failed', { error: 'private' }))
  expect(screen.queryByRole('button', { name: /Retry/ })).toBeNull()
})

test('the page: look up, add, clear finished', async () => {
  py.lookup.mockResolvedValue({ ok: true, data: { kind: 'video', info } })
  py.add_to_queue.mockResolvedValue({ ok: true, data: { taskIds: ['t'] } })
  render(<App />)
  const box = screen.getByLabelText('Video or playlist URL')
  fireEvent.change(box, { target: { value: 'https://youtu.be/v' } })
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Look up' })))
  await settle()
  expect(py.lookup).toHaveBeenCalledWith('https://youtu.be/v')
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Add to queue' })))
  await settle()
  expect(py.add_to_queue).toHaveBeenCalledWith(['https://youtu.be/v'], 'mp3', 320)
  expect(document.activeElement).toBe(box)

  await send({ type: 'tasksChanged', tasks: [item('done')] })
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Clear finished' })))
  await settle()
  expect(py.clear_finished).toHaveBeenCalled()
})

test('opening a folder that moved shows a toast', async () => {
  py.open_task_folder.mockResolvedValue({ ok: true, data: { opened: 'none' } })
  render(<App />)
  await send({ type: 'tasksChanged', tasks: [item('done')] })
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Open folder: A song' })))
  await settle()
  expect(text()).toContain("Couldn't find the file or its folder")
})

// ---- focus when a row's buttons are swapped for its new status

test.each<[string, QueueItem, string, QueueItem, string]>([
  ['cancel', item('downloading', { percent: 10 }), 'Cancel: A song', item('cancelled'), 'Add again: A song'],
  ['retry', item('failed', { error: 'network' }), 'Retry: A song', item('queued'), 'Cancel: A song'],
  ['add again', item('cancelled'), 'Add again: A song', item('queued'), 'Cancel: A song'],
  ['a download ending by itself', item('downloading', { percent: 99 }), 'Cancel: A song', item('done'), 'Open folder: A song'],
  ['a failure with no retry', item('downloading'), 'Cancel: A song', item('failed', { error: 'private' }), 'Remove from queue: A song'],
])('after %s, focus stays in the row', async (_name, before, pressed, after, lands) => {
  render(<App />)
  await send({ type: 'tasksChanged', tasks: [before] })
  screen.getByRole('button', { name: pressed }).focus()
  await send({ type: 'tasksChanged', tasks: [after] })
  expect(document.activeElement).toBe(screen.getByRole('button', { name: lands }))
})

test('holding Enter on a row button counts only the first press', async () => {
  render(<App />)
  await send({ type: 'tasksChanged', tasks: [item('downloading')] })
  const button = screen.getByRole('button', { name: 'Cancel: A song' })
  // fireEvent returns false when the default was prevented; in Chromium that stops Enter clicking.
  expect(fireEvent.keyDown(button, { key: 'Enter' })).toBe(true)
  await send({ type: 'tasksChanged', tasks: [item('cancelled')] })
  // Same element, now "Add again": the held key must not add it back.
  expect(fireEvent.keyDown(button, { key: 'Enter', repeat: true })).toBe(false)
})

test('a row changing status does not pull focus that is elsewhere', async () => {
  render(<App />)
  await send({ type: 'tasksChanged', tasks: [item('downloading')] })
  const box = screen.getByLabelText('Video or playlist URL')
  box.focus()
  await send({ type: 'tasksChanged', tasks: [item('done')] })
  expect(document.activeElement).toBe(box)
})

// ---- Ctrl+V anywhere

function paste(text: string, target: Element = document.body) {
  const event = new Event('paste', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'clipboardData', { value: { getData: () => text } })
  act(() => target.dispatchEvent(event))
}

test('pasting a URL anywhere looks it up; other text only says it is not a URL', async () => {
  render(<App />)
  paste('  https://youtu.be/v ')
  await settle()
  expect(py.lookup).toHaveBeenCalledWith('https://youtu.be/v')
  paste('some words from a web page')
  expect(py.lookup).toHaveBeenCalledTimes(1)
  expect(text()).toContain("The clipboard doesn't contain a URL.")
})

test('the URL box looks up a paste only while it is empty', async () => {
  render(<App />)
  const box = screen.getByLabelText('Video or playlist URL') as HTMLInputElement
  box.focus()
  paste('https://youtu.be/v', box)
  await settle()
  expect(py.lookup).toHaveBeenCalledTimes(1)
  fireEvent.change(box, { target: { value: 'https://you' } })
  paste('tu.be/v', box)
  await settle()
  expect(py.lookup).toHaveBeenCalledTimes(1)
})

// ---- closing the window

test('closing with tasks running asks first; keeping open does not close', async () => {
  render(<App />)
  await send({ type: 'tasksChanged', tasks: [item('downloading', { percent: 5, doneBytes: 5 }), { ...item('done'), id: 'b' }] })
  await send({ type: 'closeRequested' })
  const dialog = screen.getByRole('dialog')
  expect(dialog.textContent).toContain("1 download hasn't finished")
  expect(document.activeElement?.textContent).toBe('Keep downloading')
  // The page's own cancel-all dialog is in the document too, closed: ask this one.
  await act(async () => fireEvent.click(within(dialog).getByText('Keep downloading')))
  await settle()
  expect(py.confirm_close).not.toHaveBeenCalled()
  await send({ type: 'closeRequested' })
  await act(async () => fireEvent.click(within(dialog).getByText('Stop and close')))
  await settle()
  expect(py.confirm_close).toHaveBeenCalledTimes(1)
})

test('closing when every task has finished meanwhile closes without asking', async () => {
  render(<App />)
  await send({ type: 'tasksChanged', tasks: [item('done')] })
  await send({ type: 'closeRequested' })
  expect(py.confirm_close).toHaveBeenCalledTimes(1)
})

function Bomb(): never {
  throw new Error('broken on purpose')
}

test('with the page broken, the close question still works', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  render(<App />)
  // A ready preview without its video breaks the page the way a bad reply would.
  await act(async () => usePreview.setState({ preview: { kind: 'ready', info: undefined as never } }))
  expect(text()).toContain('Something went wrong on this screen')
  expect(screen.getByRole('navigation')).toBeTruthy()
  await act(async () => handle({ type: 'tasksChanged', tasks: [item('queued')] }))
  await send({ type: 'closeRequested' })
  await act(async () => fireEvent.click(screen.getByText('Stop and close')))
  await settle()
  expect(py.confirm_close).toHaveBeenCalledTimes(1)
})

test('with everything broken, close still closes the window', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  render(
    <ErrorBoundary>
      <Bomb />
      <ConfirmCloseDialog />
    </ErrorBoundary>,
  )
  expect(text()).toContain('Something went wrong on this screen')
  await act(async () => handle({ type: 'tasksChanged', tasks: [item('queued')] }))
  await send({ type: 'closeRequested' })
  expect(py.confirm_close).toHaveBeenCalledTimes(1)
})
