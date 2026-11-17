// The stores against a stand-in api/: no window, no Python. Each test sets the replies it
// needs; deferred() lets a test decide when a lookup answers.

import { beforeEach, expect, test, vi } from 'vitest'
import type { DataEvent } from '../api'
import type { LookupResult, MediaInfo, QueueItem, Settings } from '../types'

const api = vi.hoisted(() => ({
  lookup: vi.fn(),
  addToQueue: vi.fn(),
  getQueue: vi.fn(),
  getSettings: vi.fn(),
  onEvent: vi.fn(),
  removeTask: vi.fn(),
  clearFinished: vi.fn(),
  openTaskFolder: vi.fn(),
  checkAppUpdate: vi.fn(),
}))
vi.mock('../api', () => api)
vi.mock('../i18n', () => ({ default: { language: 'zh-TW', changeLanguage: vi.fn() }, systemLanguage: () => 'zh-TW' }))

const { usePreview, lookUp, closePreview, addPreview, choose, resetPreview, resolve } = await import('./preview')
const { useQueue, resetQueue, openFolder, clearFinished } = await import('./queue')
const { useNotices } = await import('./notices')
const { useSettings } = await import('./settings')
const { start, handle } = await import('./start')

const ok = <T>(data?: T) => ({ ok: true as const, data })

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => (resolve = r))
  return { promise, resolve }
}

const video = (url: string, heights = [360, 720, 1080]): MediaInfo => ({
  url,
  title: `title of ${url}`,
  durationSec: 60,
  platform: 'youtube',
  options: [
    { format: 'mp3', quality: 128 },
    { format: 'mp3', quality: 320 },
    ...heights.map((quality) => ({ format: 'mp4' as const, quality })),
  ],
})
const found = (info: MediaInfo) => ok<LookupResult>({ kind: 'video', info })

const item = (id: string, more: Partial<QueueItem> = {}): QueueItem => ({
  id,
  url: `https://youtu.be/${id}`,
  format: 'mp3',
  quality: 320,
  status: 'queued',
  ...more,
})

const settings: Settings = {
  downloadDir: 'D:\\Downloads',
  maxConcurrent: 3,
  onDuplicate: 'rename',
  format: 'mp4',
  mp3Bitrate: 192,
  mp4Height: 720,
  language: 'zh-TW',
}

const flush = () => new Promise((r) => setTimeout(r, 0))
const spoken = () => useNotices.getState().spoken.map((n) => n.key)

beforeEach(() => {
  vi.clearAllMocks()
  resetPreview()
  resetQueue()
  useSettings.setState({ settings: undefined })
  useNotices.setState({ toast: undefined, spoken: [] })
  api.addToQueue.mockResolvedValue(ok({ taskIds: ['t'] }))
  api.checkAppUpdate.mockResolvedValue(ok({ currentVersion: '0.1.0' }))
})

// ---- start and events

test('start listens before it asks for the queue, the settings and a newer app', () => {
  const order: string[] = []
  api.onEvent.mockImplementation(() => (order.push('onEvent'), () => {}))
  api.getQueue.mockImplementation(() => (order.push('getQueue'), new Promise(() => {})))
  api.getSettings.mockImplementation(() => (order.push('getSettings'), new Promise(() => {})))
  api.checkAppUpdate.mockImplementation(() => (order.push('checkAppUpdate'), new Promise(() => {})))
  start()
  expect(order[0]).toBe('onEvent')
  expect(order.slice(1).sort()).toEqual(['checkAppUpdate', 'getQueue', 'getSettings'])
})

test('events that arrive before getQueue answers win over the reply', async () => {
  const queue = deferred<unknown>()
  api.onEvent.mockReturnValue(() => {})
  api.getQueue.mockReturnValue(queue.promise)
  api.getSettings.mockReturnValue(new Promise(() => {}))
  start()
  handle({ type: 'tasksChanged', tasks: [item('a', { status: 'done' }), item('new')] })
  handle({ type: 'tasksRemoved', ids: ['gone'] })
  queue.resolve(ok([item('a', { status: 'downloading' }), item('b'), item('gone', { status: 'done' })]))
  await flush()
  const { items, loaded } = useQueue.getState()
  expect(loaded).toBe(true)
  expect(items.map((i) => [i.id, i.status])).toEqual([
    ['b', 'queued'],
    ['a', 'done'],
    ['new', 'queued'],
  ])
})

test('tasksChanged replaces known items in place and appends new ones', () => {
  handle({ type: 'tasksChanged', tasks: [item('a'), item('b')] })
  handle({ type: 'tasksChanged', tasks: [item('c'), item('a', { status: 'downloading', percent: 0, doneBytes: 0 })] })
  expect(useQueue.getState().items.map((i) => [i.id, i.status])).toEqual([
    ['a', 'downloading'],
    ['b', 'queued'],
    ['c', 'queued'],
  ])
})

test('taskProgress replaces all five fields, so one it leaves out is gone', () => {
  handle({
    type: 'tasksChanged',
    tasks: [item('a', { status: 'downloading', percent: 40, doneBytes: 4, totalBytes: 10, speedBps: 1, etaSec: 6 })],
  })
  handle({ type: 'taskProgress', progress: { id: 'a', percent: 50, doneBytes: 5 } })
  const [a] = useQueue.getState().items
  expect(a).toMatchObject({ percent: 50, doneBytes: 5 })
  expect(a.totalBytes).toBeUndefined()
  expect(a.speedBps).toBeUndefined()
  expect(a.etaSec).toBeUndefined()
})

test('a late progress event does not bring numbers back to a converting task', () => {
  handle({ type: 'tasksChanged', tasks: [item('a', { status: 'converting' })] })
  handle({ type: 'taskProgress', progress: { id: 'a', percent: 99, doneBytes: 9 } })
  expect(useQueue.getState().items[0].percent).toBeUndefined()
})

test('a lost tasksChanged is put right by the next one', () => {
  handle({ type: 'tasksChanged', tasks: [item('a', { status: 'downloading', percent: 30, doneBytes: 3 })] })
  // converting never arrives
  handle({ type: 'taskProgress', progress: { id: 'a', percent: 31, doneBytes: 3 } })
  handle({ type: 'tasksChanged', tasks: [item('a', { status: 'done', sizeBytes: 5 })] })
  expect(useQueue.getState().items).toEqual([item('a', { status: 'done', sizeBytes: 5 })])
})

test('tasksRemoved takes the items away', () => {
  handle({ type: 'tasksChanged', tasks: [item('a'), item('b'), item('c')] })
  handle({ type: 'tasksRemoved', ids: ['a', 'c'] })
  expect(useQueue.getState().items.map((i) => i.id)).toEqual(['b'])
})

test('only finishing, failing and losing the connection are read out', () => {
  handle({ type: 'tasksChanged', tasks: [item('a'), item('b'), item('c')] })
  const steps: DataEvent[] = [
    { type: 'tasksChanged', tasks: [item('a', { status: 'downloading', percent: 0, doneBytes: 0 })] },
    { type: 'taskProgress', progress: { id: 'a', percent: 10, doneBytes: 1 } },
    { type: 'tasksChanged', tasks: [item('a', { status: 'retrying', attempt: 1 })] },
    { type: 'tasksChanged', tasks: [item('a', { status: 'retrying', attempt: 2 })] },
    { type: 'tasksChanged', tasks: [item('a', { status: 'converting' })] },
    { type: 'tasksChanged', tasks: [item('a', { status: 'done', sizeBytes: 1 })] },
    { type: 'tasksChanged', tasks: [item('b', { status: 'failed', error: 'network' })] },
    { type: 'tasksChanged', tasks: [item('c', { status: 'done', skipped: true })] },
  ]
  const heard: string[] = []
  const stop = useNotices.subscribe((s) => heard.push(s.spoken.at(-1)!.key))
  steps.forEach(handle)
  stop()
  expect(heard).toEqual(['live.retrying', 'live.done', 'live.failed', 'live.skipped'])
})

test('settingsChanged updates the settings and an untouched preview, not a touched one', async () => {
  api.lookup.mockResolvedValue(found(video('https://youtu.be/x')))
  await lookUp('https://youtu.be/x')
  expect(usePreview.getState().choice.format).toBe('mp3')
  handle({ type: 'settingsChanged', settings })
  expect(useSettings.getState().settings).toEqual(settings)
  expect(usePreview.getState().choice).toEqual({ format: 'mp4', mp3Bitrate: 192, mp4Height: 720 })
  choose({ format: 'mp3' })
  handle({ type: 'settingsChanged', settings: { ...settings, mp3Bitrate: 128 } })
  expect(usePreview.getState().choice.mp3Bitrate).toBe(192)
})

// ---- preview

test('a preview starts from what was used last', async () => {
  useSettings.setState({ settings })
  api.lookup.mockResolvedValue(found(video('https://youtu.be/x')))
  await lookUp('  https://youtu.be/x  ')
  expect(api.lookup).toHaveBeenCalledWith('https://youtu.be/x')
  expect(usePreview.getState().choice).toEqual({ format: 'mp4', mp3Bitrate: 192, mp4Height: 720 })
})

test('the remembered height is a ceiling; a video without picture is MP3 only', () => {
  const choice = { format: 'mp4' as const, mp3Bitrate: 320, mp4Height: 1080 }
  expect(resolve(video('u', [240, 480]), choice)).toEqual({ format: 'mp4', quality: 480 })
  expect(resolve(video('u', [1440, 2160]), choice)).toEqual({ format: 'mp4', quality: 1440 })
  expect(resolve(video('u', []), choice)).toEqual({ format: 'mp3', quality: 320 })
})

test('a lookup that answers after the preview was closed is thrown away', async () => {
  const late = deferred<unknown>()
  api.lookup.mockReturnValue(late.promise)
  const done = lookUp('https://youtu.be/x')
  closePreview()
  late.resolve(found(video('https://youtu.be/x')))
  await done
  expect(usePreview.getState().preview).toBeNull()
})

test('a lookup that answers after a newer URL was pasted is thrown away', async () => {
  const first = deferred<unknown>()
  api.lookup.mockReturnValueOnce(first.promise).mockResolvedValueOnce(found(video('https://youtu.be/two')))
  const one = lookUp('https://youtu.be/one')
  await lookUp('https://youtu.be/two')
  first.resolve(found(video('https://youtu.be/one')))
  await one
  const { preview } = usePreview.getState()
  expect(preview?.kind === 'ready' && preview.info.url).toBe('https://youtu.be/two')
})

test('pasting over a found preview adds it with the choice on screen', async () => {
  api.lookup.mockResolvedValueOnce(found(video('https://youtu.be/one'))).mockReturnValueOnce(new Promise(() => {}))
  await lookUp('https://youtu.be/one')
  choose({ format: 'mp4', mp4Height: 720 })
  void lookUp('https://youtu.be/two')
  await flush()
  expect(api.addToQueue).toHaveBeenCalledWith(['https://youtu.be/one'], 'mp4', 720)
  expect(spoken()).toEqual(['queue.autoAdded'])
  expect(usePreview.getState().preview).toEqual({ kind: 'loading', url: 'https://youtu.be/two', started: expect.any(Number) })
})

test('pasting over a preview still looking adds its URL alone, to be looked up in the queue', async () => {
  useSettings.setState({ settings })
  api.lookup.mockReturnValue(new Promise(() => {}))
  void lookUp('https://youtu.be/one')
  void lookUp('https://youtu.be/two')
  await flush()
  expect(api.addToQueue).toHaveBeenCalledWith(['https://youtu.be/one'], 'mp4', 720)
  expect(usePreview.getState().preview).toEqual({ kind: 'loading', url: 'https://youtu.be/two', started: expect.any(Number) })
})

test('pasting over a failed preview or a playlist only replaces it', async () => {
  api.lookup
    .mockResolvedValueOnce({ ok: false, error: 'private' })
    .mockResolvedValueOnce(ok({ kind: 'playlist', playlist: { url: 'p', title: 'p', platform: 'youtube', entries: [] } }))
    .mockReturnValueOnce(new Promise(() => {}))
  await lookUp('https://youtu.be/private')
  expect(usePreview.getState().preview).toMatchObject({ kind: 'error', code: 'private' })
  await lookUp('https://youtube.com/playlist?list=p')
  expect(usePreview.getState().preview?.kind).toBe('playlist')
  void lookUp('https://youtu.be/three')
  await flush()
  expect(api.addToQueue).not.toHaveBeenCalled()
})

test('the add button adds, closes the preview and says so', async () => {
  api.lookup.mockResolvedValue(found(video('https://youtu.be/x')))
  await lookUp('https://youtu.be/x')
  expect(await addPreview()).toBe(true)
  expect(api.addToQueue).toHaveBeenCalledWith(['https://youtu.be/x'], 'mp3', 320)
  expect(usePreview.getState().preview).toBeNull()
  expect(spoken()).toEqual(['live.added'])
})

test('an add that fails shows its error in the preview', async () => {
  api.lookup.mockResolvedValue(found(video('https://youtu.be/x')))
  api.addToQueue.mockResolvedValue({ ok: false, error: 'invalidUrl' })
  await lookUp('https://youtu.be/x')
  expect(await addPreview()).toBe(false)
  expect(usePreview.getState().preview).toEqual({ kind: 'error', url: 'https://youtu.be/x', code: 'invalidUrl' })
})

// ---- queue actions

test('opening a folder speaks up only when the file itself was not shown', async () => {
  const toast = () => useNotices.getState().toast?.key
  api.openTaskFolder.mockResolvedValueOnce(ok({ opened: 'file' }))
  await openFolder('a')
  expect(toast()).toBeUndefined()
  api.openTaskFolder.mockResolvedValueOnce(ok({ opened: 'folder' }))
  await openFolder('a')
  expect(toast()).toBe('toast.openedFolder')
  api.openTaskFolder.mockResolvedValueOnce(ok({ opened: 'none' }))
  await openFolder('a')
  expect(toast()).toBe('toast.notFound')
  api.openTaskFolder.mockResolvedValueOnce({ ok: false, error: 'unknown' })
  useNotices.setState({ toast: undefined })
  await openFolder('a')
  expect(toast()).toBe('toast.notFound')
})

test('clear finished reads out how many went', async () => {
  handle({ type: 'tasksChanged', tasks: [item('a', { status: 'done' }), item('b', { status: 'failed' }), item('c')] })
  api.clearFinished.mockResolvedValue(ok())
  await clearFinished()
  expect(useNotices.getState().spoken.at(-1)).toMatchObject({ key: 'live.removed', params: { count: 2 } })
})
