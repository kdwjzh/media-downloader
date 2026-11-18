// @vitest-environment jsdom
// The playlist screen, cancel-all and the long queue, against a stand-in for pywebview:
// the real api/ and stores, a fake window.pywebview.api. No Python.

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, expect, test, vi } from 'vitest'
import type { PlaylistEntry, PlaylistInfo, QueueItem } from '../types'

const COMMANDS = ['ping', 'lookup', 'add_to_queue', 'get_queue', 'get_settings', 'cancel_task', 'confirm_close']
const py: Record<string, ReturnType<typeof vi.fn>> = Object.fromEntries(COMMANDS.map((name) => [name, vi.fn()]))
window.pywebview = { api: py as never }

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
const { usePreview, resetPreview, choose } = await import('../stores/preview')
const { resetQueue, loadQueue } = await import('../stores/queue')
const { useNotices } = await import('../stores/notices')

const settle = () => act(() => new Promise<void>((r) => setTimeout(r, 0)))

const entry = (n: number, more: Partial<PlaylistEntry> = {}): PlaylistEntry => ({
  url: `https://www.youtube.com/watch?v=v${n}`,
  title: `Song ${n}`,
  channel: `Singer ${n}`,
  durationSec: 200 + n,
  available: true,
  ...more,
})
// The third one is private: only its URL is known (contract 2.4).
const FIVE = [entry(1), entry(2), { url: 'https://www.youtube.com/watch?v=gone', available: false }, entry(4), entry(5)]
const playlist = (entries: PlaylistEntry[], title = 'Top songs'): PlaylistInfo => ({
  url: 'https://www.youtube.com/playlist?list=PL1',
  title,
  channel: 'Charts',
  platform: 'youtube',
  entries,
})

function show(entries: PlaylistEntry[] = FIVE) {
  usePreview.setState({ preview: { kind: 'playlist', playlist: playlist(entries) } })
  return render(<App />)
}

const all = () => screen.getByRole('checkbox', { name: 'Select all' }) as HTMLInputElement
const listbox = () => screen.getByRole('listbox')
const options = () => within(listbox()).getAllByRole('option')
const addButton = () => screen.getByRole('button', { name: /to queue$/ }) as HTMLButtonElement
const text = () => document.body.textContent

beforeEach(async () => {
  for (const fn of Object.values(py)) fn.mockReset().mockResolvedValue({ ok: true })
  py.ping.mockResolvedValue({ ok: true, data: 'pong' })
  py.lookup.mockReturnValue(new Promise(() => {}))
  py.add_to_queue.mockResolvedValue({ ok: true, data: { taskIds: [] } })
  await i18n.changeLanguage('en')
  resetQueue()
  loadQueue([])
  resetPreview()
  useNotices.setState({ spoken: [], toast: undefined })
})

afterEach(cleanup)

// ---- 8: ticking

test('everything that can be downloaded starts ticked; the private one cannot be and does not count', () => {
  show()
  expect(text()).toContain('Top songs')
  expect(text()).toContain('5 videos')
  expect(text()).toContain('4 of 4 selected')
  expect(all().checked).toBe(true)
  expect(all().indeterminate).toBe(false)
  const gone = options()[2]
  expect(gone.getAttribute('aria-disabled')).toBe('true')
  expect(gone.getAttribute('aria-selected')).toBe('false')
  expect(gone.textContent).toContain('https://www.youtube.com/watch?v=gone')
  expect(gone.textContent).toContain('Unavailable')
  fireEvent.click(gone)
  expect(gone.getAttribute('aria-selected')).toBe('false')
  expect(text()).toContain('4 of 4 selected')
  expect(addButton().textContent).toBe('Add 4 to queue')
})

test('select all has three states; some ticked turns into all', () => {
  show()
  fireEvent.click(options()[0]) // a whole row toggles
  expect(text()).toContain('3 of 4 selected')
  expect(all().checked).toBe(false)
  expect(all().indeterminate).toBe(true)
  fireEvent.click(all())
  expect(text()).toContain('4 of 4 selected')
  expect(all().indeterminate).toBe(false)
  fireEvent.click(all())
  expect(text()).toContain('0 of 4 selected')
  expect(all().checked).toBe(false)
  expect(all().indeterminate).toBe(false)
})

test('nothing ticked: the add button is off and a hint says why', () => {
  show()
  fireEvent.click(all())
  expect(addButton().disabled).toBe(true)
  expect(addButton().textContent).toBe('Add 0 to queue')
  expect(text()).toContain('Select at least one item')
})

test('one ticked reads in the singular; a title without a length still counts', () => {
  show([entry(1, { durationSec: undefined }), { url: 'https://youtu.be/x', available: false }])
  expect(text()).toContain('2 videos')
  expect(text()).toContain('1 of 1 selected')
  expect(addButton().textContent).toBe('Add 1 to queue')
})

test('an empty playlist says so, and nothing can be added', () => {
  show([])
  expect(text()).toContain('This playlist has no videos')
  expect(all().disabled).toBe(true)
  expect(addButton().disabled).toBe(true)
})

// ---- 9: the keyboard

test('the list is one tab stop; arrows move, Space ticks, Home and End jump', () => {
  show()
  const list = listbox()
  expect(list.tabIndex).toBe(0)
  for (const option of options()) expect(option.hasAttribute('tabindex')).toBe(false)
  const active = () => document.getElementById(list.getAttribute('aria-activedescendant')!)
  list.focus()
  expect(active()?.textContent).toContain('Song 1')
  fireEvent.keyDown(list, { key: ' ' })
  expect(active()?.getAttribute('aria-selected')).toBe('false')
  fireEvent.keyDown(list, { key: 'ArrowDown' })
  fireEvent.keyDown(list, { key: 'ArrowDown' })
  expect(active()?.getAttribute('aria-disabled')).toBe('true')
  fireEvent.keyDown(list, { key: ' ' }) // the private one stays unticked
  expect(active()?.getAttribute('aria-selected')).toBe('false')
  fireEvent.keyDown(list, { key: 'End' })
  expect(active()?.textContent).toContain('Song 5')
  fireEvent.keyDown(list, { key: 'ArrowDown' }) // stops at the end
  expect(active()?.textContent).toContain('Song 5')
  fireEvent.keyDown(list, { key: 'Home' })
  fireEvent.keyDown(list, { key: 'ArrowUp' })
  expect(active()?.textContent).toContain('Song 1')
  expect(text()).toContain('3 of 4 selected')
})

test('holding Space ticks once; a held arrow still moves', () => {
  show()
  const list = listbox()
  const active = () => document.getElementById(list.getAttribute('aria-activedescendant')!)
  list.focus()
  fireEvent.keyDown(list, { key: ' ' })
  // Repeats of a held key: still no scrolling, but the tick stays as the first press left it.
  expect(fireEvent.keyDown(list, { key: ' ', repeat: true })).toBe(false)
  expect(active()?.getAttribute('aria-selected')).toBe('false')
  fireEvent.keyDown(list, { key: ' ', repeat: true })
  expect(active()?.getAttribute('aria-selected')).toBe('false')
  fireEvent.keyDown(list, { key: 'ArrowDown', repeat: true })
  expect(active()?.textContent).toContain('Song 2')
})

// ---- 10: adding

test('adding sends the ticked URLs in the list order with the MP3 choice', async () => {
  show()
  fireEvent.click(options()[3]) // untick Song 4
  choose({ mp3Bitrate: 192 })
  await act(async () => fireEvent.click(addButton()))
  await settle()
  expect(py.add_to_queue).toHaveBeenCalledWith(
    ['https://www.youtube.com/watch?v=v1', 'https://www.youtube.com/watch?v=v2', 'https://www.youtube.com/watch?v=v5'],
    'mp3',
    192,
  )
  // Back to the main screen; focus waits in the URL box for the next paste.
  expect(usePreview.getState().preview).toBeNull()
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(document.activeElement).toBe(screen.getByLabelText('Video or playlist URL'))
  expect(useNotices.getState().spoken.at(-1)).toMatchObject({ key: 'live.addedMany', params: { count: 3 } })
})

test('MP4 lists every height as a ceiling and sends the ceiling', async () => {
  show()
  fireEvent.click(screen.getByRole('radio', { name: 'MP4' }))
  const select = screen.getByLabelText('Video quality') as HTMLSelectElement
  expect([...select.options].map((o) => o.text)).toEqual([
    'Up to 2160p', 'Up to 1440p', 'Up to 1080p', 'Up to 720p', 'Up to 480p', 'Up to 360p', 'Up to 240p', 'Up to 144p',
  ])
  fireEvent.change(select, { target: { value: '720' } })
  await act(async () => fireEvent.click(addButton()))
  await settle()
  expect(py.add_to_queue).toHaveBeenCalledWith(expect.any(Array), 'mp4', 720)
})

test('a second click while adding sends nothing more', async () => {
  let answer: (value: unknown) => void = () => {}
  py.add_to_queue.mockReturnValue(new Promise((r) => (answer = r)))
  show()
  await act(async () => fireEvent.click(addButton()))
  expect(addButton().disabled).toBe(true)
  fireEvent.click(addButton())
  expect(py.add_to_queue).toHaveBeenCalledTimes(1)
  await act(async () => answer({ ok: true, data: { taskIds: [] } }))
})

test('Cancel and the close button go back with the queue as it was', async () => {
  loadQueue([{ id: 'q', url: 'https://youtu.be/q', title: 'Already here', format: 'mp3', quality: 320, status: 'queued' }])
  for (const name of ['Cancel', 'Close playlist']) {
    show()
    expect(text()).not.toContain('Already here') // the list stands in for the queue
    fireEvent.click(screen.getByRole('button', { name }))
    expect(text()).toContain('Already here')
    expect(py.add_to_queue).not.toHaveBeenCalled()
    cleanup()
  }
})

// ---- 11: pasting while the list is open, and late answers

function paste(text: string) {
  const event = new Event('paste', { bubbles: true }) as ClipboardEvent
  Object.defineProperty(event, 'clipboardData', { value: { getData: () => text } })
  act(() => void document.body.dispatchEvent(event))
}

test('a new URL pasted over the list replaces it and adds nothing', async () => {
  show()
  paste('https://youtu.be/next')
  await settle()
  expect(py.lookup).toHaveBeenCalledWith('https://youtu.be/next')
  expect(py.add_to_queue).not.toHaveBeenCalled()
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(usePreview.getState().preview).toMatchObject({ kind: 'loading', url: 'https://youtu.be/next' })
})

test('a playlist answer that comes after a newer paste is thrown away', async () => {
  let first: (value: unknown) => void = () => {}
  py.lookup.mockReturnValueOnce(new Promise((r) => (first = r)))
  render(<App />)
  paste('https://www.youtube.com/playlist?list=PL1')
  paste('https://youtu.be/next')
  await act(async () => first({ ok: true, data: { kind: 'playlist', playlist: playlist(FIVE) } }))
  await settle()
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(usePreview.getState().preview).toMatchObject({ kind: 'loading', url: 'https://youtu.be/next' })
})

test('a playlist that cannot be found shows like a failed preview', async () => {
  py.lookup.mockResolvedValue({ ok: false, error: 'playlistNotFound' })
  render(<App />)
  paste('https://www.youtube.com/playlist?list=PLgone')
  await settle()
  expect(screen.getByRole('alert').textContent).toContain('Playlist not found')
  expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull()
})

// ---- 12: a long list

function scrollTo(el: HTMLElement, top: number) {
  Object.defineProperty(el, 'scrollTop', { value: top, configurable: true, writable: true })
  fireEvent.scroll(el)
}

test('1,700 entries: drawn and scrollable, only the rows near the view exist', () => {
  const many = Array.from({ length: 1700 }, (_, i) => (i % 211 === 17 ? { url: `https://youtu.be/x${i}`, available: false } : entry(i)))
  const t0 = performance.now()
  show(many)
  const drawn = performance.now() - t0
  expect(text()).toContain('1,700 videos')
  expect(text()).toContain('1,692 of 1,692 selected')
  expect(options().length).toBeLessThan(30)

  const t1 = performance.now()
  scrollTo(listbox(), 56 * 1000)
  const scrolled = performance.now() - t1
  expect(options().some((o) => o.textContent?.includes('Song 1000'))).toBe(true)
  expect(options().length).toBeLessThan(30)
  // Every row says where it sits in the whole list.
  expect(options()[0].getAttribute('aria-setsize')).toBe('1700')

  const t2 = performance.now()
  fireEvent.click(all())
  const untickAll = performance.now() - t2
  expect(text()).toContain('0 of 1,692 selected')
  console.info(`1,700 entries (jsdom): first draw ${drawn.toFixed(0)} ms, scroll ${scrolled.toFixed(0)} ms, untick all ${untickAll.toFixed(0)} ms`)
})

test('End reaches the last of 1,700 and keeps it drawn', () => {
  show(Array.from({ length: 1700 }, (_, i) => entry(i)))
  const list = listbox()
  list.focus()
  fireEvent.keyDown(list, { key: 'End' })
  expect(document.getElementById(list.getAttribute('aria-activedescendant')!)?.textContent).toContain('Song 1699')
})

// ---- the queue after a big batch, and cancel all

const task = (n: number, status: QueueItem['status']): QueueItem => ({
  id: `t${n}`,
  url: `https://youtu.be/t${n}`,
  title: `Task ${n}`,
  format: 'mp3',
  quality: 320,
  status,
})

test('a queue of 1,000 draws only the rows near the view', () => {
  loadQueue(Array.from({ length: 1000 }, (_, i) => task(i, 'queued')))
  const t0 = performance.now()
  render(<App />)
  const drawn = performance.now() - t0
  expect(text()).toContain('Queue (1,000)')
  expect(screen.getAllByText('Waiting').length).toBeLessThan(30)
  console.info(`queue of 1,000 (jsdom): first draw ${drawn.toFixed(0)} ms`)
})

test('cancel all asks first, then cancels the waiting tasks before the running ones', async () => {
  loadQueue([task(1, 'downloading'), task(2, 'queued'), task(3, 'done'), task(4, 'queued')])
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel all' }))
  const dialog = screen.getByRole('dialog')
  expect(dialog.textContent).toContain("3 items haven't finished. Cancel them all?")
  expect(document.activeElement?.textContent).toBe('Keep downloading')
  await act(async () => fireEvent.click(within(dialog).getByText('Keep downloading')))
  expect(py.cancel_task).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: 'Cancel all' }))
  await act(async () => fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel all' })))
  await settle()
  expect(py.cancel_task.mock.calls).toEqual([['t2'], ['t4'], ['t1']])
})

// Bug found in the author's 4c acceptance: opened by a mouse click, the dialog put focus on
// "Keep downloading" but drew no ring, because Chromium shows :focus-visible after script
// focus only when the last input was the keyboard. jsdom draws nothing, so the test checks
// that the ring is asked for.
test('the safe answer of a dialog opened by mouse still shows its focus ring', () => {
  const focus = vi.spyOn(HTMLElement.prototype, 'focus')
  loadQueue([task(1, 'queued')])
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel all' }))
  const keep = within(screen.getByRole('dialog')).getByText('Keep downloading')
  expect(focus.mock.contexts.at(-1)).toBe(keep)
  expect(focus.mock.calls.at(-1)).toEqual([{ focusVisible: true }])
  focus.mockRestore()
})

test('cancel all only shows while something is unfinished', () => {
  loadQueue([task(1, 'done'), task(2, 'cancelled')])
  render(<App />)
  expect(screen.queryByRole('button', { name: 'Cancel all' })).toBeNull()
})
