// @vitest-environment jsdom
// The history screen and switching screens, against a stand-in for pywebview: the real
// api/ and stores, a fake window.pywebview.api. No Python.

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, expect, test, vi } from 'vitest'
import type { BackendEvent, HistoryEntry, PlaylistInfo, QueueItem } from '../types'

const COMMANDS = [
  'ping', 'lookup', 'add_to_queue', 'get_queue', 'get_settings', 'cancel_task', 'confirm_close',
  'list_history', 'redownload_history', 'open_history_folder', 'delete_history', 'clear_history',
]
const py: Record<string, ReturnType<typeof vi.fn>> = Object.fromEntries(COMMANDS.map((name) => [name, vi.fn()]))
window.pywebview = { api: py as never }
vi.stubEnv('TZ', 'Asia/Taipei') // the times below are written in Taipei time

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
const { resetHistory, useHistory } = await import('../stores/history')
const { usePage } = await import('../stores/page')
const { usePreview, resetPreview } = await import('../stores/preview')
const { resetQueue, loadQueue } = await import('../stores/queue')
const { useNotices } = await import('../stores/notices')
const { handle } = await import('../stores/start')
const { onEvent } = await import('../api')
onEvent(handle)

const settle = () => act(() => new Promise<void>((r) => setTimeout(r, 0)))
const send = async (event: BackendEvent) => {
  await act(async () => window.mediaDownloaderEvent?.(event))
  await settle()
}

const MB = 1024 * 1024
const entry = (n: number, more: Partial<HistoryEntry> = {}): HistoryEntry => ({
  id: `h${n}`,
  url: `https://youtu.be/v${n}`,
  title: `Song ${n}`,
  format: 'mp3',
  quality: 320,
  sizeBytes: 9 * MB,
  finishedAt: '2026-11-13T06:20:00Z',
  thumb: `data:image/jpeg;base64,AAA${n}`,
  ...more,
})
const THREE = [entry(1), entry(2, { format: 'mp4', quality: 1080, thumb: undefined }), entry(3)]

const nav = (name: string) =>
  within(screen.getByRole('navigation')).getByRole('button', { name: new RegExp(`^${name}`) })
const rows = () => [...document.querySelectorAll<HTMLElement>('#history-title ~ * li[data-id], ul[aria-labelledby="history-title"] li[data-id]')]
const rowOf = (id: string) => document.querySelector<HTMLElement>(`ul[aria-labelledby="history-title"] li[data-id="${id}"]`)!

async function openHistory(list: HistoryEntry[] = THREE) {
  py.list_history.mockResolvedValue({ ok: true, data: list })
  render(<App />)
  fireEvent.click(nav('History'))
  await settle()
}

beforeEach(async () => {
  for (const fn of Object.values(py)) fn.mockReset().mockResolvedValue({ ok: true })
  py.lookup.mockReturnValue(new Promise(() => {}))
  py.list_history.mockResolvedValue({ ok: true, data: [] })
  await i18n.changeLanguage('en')
  resetQueue()
  loadQueue([])
  resetPreview()
  resetHistory()
  usePage.setState({ page: 'downloads', urlFocus: 0 })
  useNotices.setState({ toast: undefined, spoken: [] })
})
afterEach(cleanup)

// ---- the list

test('the list keeps the order it came in, newest first, and loads once', async () => {
  await openHistory()
  expect(rows().map((r) => r.dataset.id)).toEqual(['h1', 'h2', 'h3'])
  fireEvent.click(nav('Downloads'))
  fireEvent.click(nav('History'))
  await settle()
  expect(py.list_history).toHaveBeenCalledTimes(1)
})

test('times are local time in the language of the interface', async () => {
  await openHistory([entry(1)])
  expect(rowOf('h1').textContent).toMatch(/Nov 13, 2026, 2:20\sPM9\.0 MB/)
  await act(() => i18n.changeLanguage('zh-TW'))
  expect(rowOf('h1').textContent).toContain('2026年11月13日 下午2:20')
})

test('an MP3 cover is square, an MP4 one 16:9, and no thumbnail leaves the placeholder', async () => {
  await openHistory()
  const box = (id: string) => rowOf(id).querySelector('[aria-hidden="true"] > div')!
  expect(box('h1').className).toContain('size-13')
  expect(box('h1').querySelector('img')?.getAttribute('src')).toBe('data:image/jpeg;base64,AAA1')
  expect(box('h2').className).toContain('h-13 w-23')
  expect(box('h2').querySelector('img')).toBeNull()
})

test('a list that fails to load says so and can be retried', async () => {
  py.list_history.mockResolvedValueOnce({ ok: false, error: 'unknown' })
  await openHistory()
  expect(screen.getByRole('alert').textContent).toContain("Couldn't read the history.")
  fireEvent.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Retry' }))
  await settle()
  expect(rows()).toHaveLength(3)
})

// ---- the buttons

test('download again adds it, marks the row and says so; the URL box is untouched', async () => {
  py.redownload_history.mockResolvedValue({ ok: true, data: { taskId: 't1' } })
  await openHistory()
  fireEvent.click(within(rowOf('h2')).getByRole('button', { name: 'Download again: Song 2' }))
  await settle()
  expect(py.redownload_history).toHaveBeenCalledWith('h2')
  expect(rowOf('h2').textContent).toContain('Queued')
  expect(rowOf('h1').textContent).not.toContain('Queued')
  expect(useNotices.getState().spoken.at(-1)).toMatchObject({ key: 'live.added', params: { title: 'Song 2' } })
  expect(usePage.getState().page).toBe('history')
})

test('download again on an entry that no longer exists takes the row away', async () => {
  py.redownload_history.mockResolvedValue({ ok: true, data: {} })
  await openHistory()
  fireEvent.click(within(rowOf('h1')).getByRole('button', { name: 'Download again: Song 1' }))
  await settle()
  expect(useNotices.getState().toast?.key).toBe('history.gone')
  expect(rows().map((r) => r.dataset.id)).toEqual(['h2', 'h3'])
})

test('open folder asks by entry id and shows the 4b toasts', async () => {
  await openHistory()
  py.open_history_folder.mockResolvedValueOnce({ ok: true, data: { opened: 'none' } })
  fireEvent.click(within(rowOf('h3')).getByRole('button', { name: 'Open folder: Song 3' }))
  await settle()
  expect(py.open_history_folder).toHaveBeenCalledWith('h3')
  expect(useNotices.getState().toast?.key).toBe('toast.notFound')
})

test('after a delete, focus goes to the delete button now in that place', async () => {
  await openHistory()
  const del = (id: string) => within(rowOf(id)).getByRole('button', { name: new RegExp(`^Delete this entry: Song ${id[1]}`) })
  fireEvent.click(del('h2'))
  await settle()
  expect(py.delete_history).toHaveBeenCalledWith('h2')
  expect(document.activeElement).toBe(del('h3'))
  // The last one: focus goes up a row.
  fireEvent.click(del('h3'))
  await settle()
  expect(document.activeElement).toBe(del('h1'))
  // None left: the empty screen's button.
  fireEvent.click(del('h1'))
  await settle()
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Go to Downloads' }))
  expect(useNotices.getState().spoken.at(-1)).toMatchObject({ key: 'history.deleted', params: { title: 'Song 1' } })
})

test('holding Enter on delete deletes one entry, not every row focus lands on', async () => {
  await openHistory()
  const del = within(rowOf('h1')).getByRole('button', { name: /^Delete this entry: Song 1/ })
  // jsdom never turns Enter into a click; in Chromium a keydown whose default is prevented
  // does not activate the button. fireEvent returns false when the default was prevented.
  expect(fireEvent.keyDown(del, { key: 'Enter' })).toBe(true)
  expect(fireEvent.keyDown(del, { key: 'Enter', repeat: true })).toBe(false)
})

test('clear history asks first: cancel keeps everything, confirming clears', async () => {
  await openHistory()
  fireEvent.click(screen.getByRole('button', { name: 'Clear history' }))
  const dialog = screen.getByRole('dialog', { name: 'Clear all 3 entries?' })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
  await settle()
  expect(py.clear_history).not.toHaveBeenCalled()
  expect(rows()).toHaveLength(3)
  fireEvent.click(screen.getByRole('button', { name: 'Clear history' }))
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Clear history' }))
  await settle()
  expect(py.clear_history).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('button', { name: 'Clear history' })).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Go to Downloads' }))
})

test('an empty history has no clear button; Go to Downloads lands in the URL box', async () => {
  await openHistory([])
  expect(screen.getByText('No downloads yet')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Clear history' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Go to Downloads' }))
  await settle()
  expect(nav('Downloads').getAttribute('aria-current')).toBe('page')
  expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Video or playlist URL' }))
})

// ---- historyAdded

test('historyAdded puts the new entry on top while the screen is open', async () => {
  await openHistory()
  await send({ type: 'historyAdded', entry: entry(9) })
  expect(rows().map((r) => r.dataset.id)).toEqual(['h9', 'h1', 'h2', 'h3'])
})

test('historyAdded before the screen ever opened is left to the first load', async () => {
  render(<App />)
  await send({ type: 'historyAdded', entry: entry(1) })
  expect(useHistory.getState().entries).toEqual([])
  py.list_history.mockResolvedValue({ ok: true, data: THREE })
  fireEvent.click(nav('History'))
  await settle()
  expect(rows().map((r) => r.dataset.id)).toEqual(['h1', 'h2', 'h3'])
})

test('historyAdded on another screen after the first load is there on return', async () => {
  await openHistory()
  fireEvent.click(nav('Downloads'))
  await send({ type: 'historyAdded', entry: entry(9) })
  fireEvent.click(nav('History'))
  await settle()
  expect(rows().map((r) => r.dataset.id)).toEqual(['h9', 'h1', 'h2', 'h3'])
  expect(py.list_history).toHaveBeenCalledTimes(1)
})

test('historyAdded while the list is on its way is neither lost nor doubled', async () => {
  let answer!: (value: unknown) => void
  py.list_history.mockReturnValue(new Promise((r) => (answer = r)))
  render(<App />)
  fireEvent.click(nav('History'))
  await send({ type: 'historyAdded', entry: entry(8) })
  await send({ type: 'historyAdded', entry: entry(9) })
  // The reply was built after the first event and before the second.
  answer({ ok: true, data: [entry(8), ...THREE] })
  await settle()
  expect(rows().map((r) => r.dataset.id)).toEqual(['h9', 'h8', 'h1', 'h2', 'h3'])
})

// ---- switching screens

test('switching away and back keeps a preview still looking, the URL box and its focus target', async () => {
  render(<App />)
  const box = screen.getByRole<HTMLInputElement>('textbox', { name: 'Video or playlist URL' })
  fireEvent.change(box, { target: { value: 'https://youtu.be/half' } })
  usePreview.setState({ preview: { kind: 'loading', url: 'https://youtu.be/x', started: Date.now() } })
  await settle()
  fireEvent.click(nav('History'))
  await settle()
  expect(box.closest('[hidden]')).not.toBeNull()
  fireEvent.click(nav('Downloads'))
  expect(box.closest('[hidden]')).toBeNull()
  expect(box.value).toBe('https://youtu.be/half')
  expect(usePreview.getState().preview?.kind).toBe('loading')
  expect(screen.getByText('Looking up video info…')).toBeTruthy()
})

test('switching away and back keeps the playlist ticks', async () => {
  const playlist: PlaylistInfo = {
    url: 'https://www.youtube.com/playlist?list=p',
    title: 'A list',
    platform: 'youtube',
    entries: [1, 2, 3].map((n) => ({ url: `https://youtu.be/p${n}`, title: `Track ${n}`, durationSec: 60, available: true })),
  }
  usePreview.setState({ preview: { kind: 'playlist', playlist } })
  render(<App />)
  fireEvent.click(within(screen.getByRole('listbox')).getAllByRole('option')[1])
  expect(document.body.textContent).toContain('2 of 3 selected')
  fireEvent.click(nav('History'))
  await settle()
  fireEvent.click(nav('Downloads'))
  expect(document.body.textContent).toContain('2 of 3 selected')
})

test('a lookup that answers on another screen is waiting in the preview on return', async () => {
  let answer!: (value: unknown) => void
  py.lookup.mockReturnValue(new Promise((r) => (answer = r)))
  render(<App />)
  const box = screen.getByRole('textbox', { name: 'Video or playlist URL' })
  fireEvent.change(box, { target: { value: 'https://youtu.be/v' } })
  fireEvent.submit(box.closest('form')!)
  fireEvent.click(nav('History'))
  answer({
    ok: true,
    data: { kind: 'video', info: { url: 'https://youtu.be/v', title: 'Late video', durationSec: 60, platform: 'youtube', options: [{ format: 'mp3', quality: 320 }] } },
  })
  await settle()
  fireEvent.click(nav('Downloads'))
  expect(screen.getByText('Late video')).toBeTruthy()
})

test('pasting a URL on the history screen goes back to Downloads and looks it up', async () => {
  await openHistory()
  const paste = new Event('paste', { bubbles: true }) as Event & { clipboardData: unknown }
  paste.clipboardData = { getData: () => 'https://youtu.be/pasted' }
  await act(async () => document.dispatchEvent(paste))
  await settle()
  expect(nav('Downloads').getAttribute('aria-current')).toBe('page')
  expect(py.lookup).toHaveBeenCalledWith('https://youtu.be/pasted')
  expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Video or playlist URL' }))
})

// ---- keyboard and the navigation

test('the navigation says where you are, and the badge counts what is not finished', async () => {
  loadQueue([
    { id: 'a', url: 'u', format: 'mp3', quality: 320, status: 'downloading' } as QueueItem,
    { id: 'b', url: 'u', format: 'mp3', quality: 320, status: 'queued' } as QueueItem,
    { id: 'c', url: 'u', format: 'mp3', quality: 320, status: 'done' } as QueueItem,
  ])
  await openHistory()
  expect(nav('History').getAttribute('aria-current')).toBe('page')
  expect(nav('Downloads').getAttribute('aria-current')).toBeNull()
  expect(nav('Downloads').textContent).toBe('Downloads2, 2 not finished')
  // Focus stays on the button pressed (decisions/0015).
  nav('Downloads').focus()
  fireEvent.click(nav('Downloads'))
  expect(document.activeElement).toBe(nav('Downloads'))
  expect(nav('Downloads').getAttribute('aria-current')).toBe('page')
})

test('Tab goes nav, then the screen; the hidden screen has nothing to reach', async () => {
  await openHistory([entry(1)])
  const reachable = [...document.querySelectorAll<HTMLElement>('button, input, [tabindex="0"]')].filter(
    (el) => !el.closest('[hidden], dialog:not([open])') && !(el as HTMLButtonElement).disabled,
  )
  const names = reachable.map((el) => el.getAttribute('aria-label') ?? el.textContent)
  expect(names).toEqual([
    expect.stringMatching(/^Downloads/),
    'History',
    'Settings',
    'Clear history',
    'Download again: Song 1',
    'Open folder: Song 1',
    'Delete this entry: Song 1',
  ])
})
