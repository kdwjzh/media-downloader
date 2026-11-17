// @vitest-environment jsdom
// The settings screen and the nav dot, against a stand-in for pywebview: the real api/ and
// stores, a fake window.pywebview.api. No Python.

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import type { AboutInfo, BackendEvent, QueueItem, Settings } from '../types'

const COMMANDS = [
  'ping', 'lookup', 'add_to_queue', 'get_queue', 'get_settings', 'update_settings', 'choose_download_folder',
  'check_app_update', 'update_engine', 'get_about', 'open_log_file', 'open_log_folder', 'open_link', 'list_history',
]
const py: Record<string, ReturnType<typeof vi.fn>> = Object.fromEntries(COMMANDS.map((name) => [name, vi.fn()]))
window.pywebview = { api: py as never }

const i18n = (await import('../i18n')).default
const { default: App } = await import('../App')
const { usePage } = await import('../stores/page')
const { resetQueue, loadQueue } = await import('../stores/queue')
const { resetPreview, usePreview } = await import('../stores/preview')
const { useNotices } = await import('../stores/notices')
const { setSettings, useSettings } = await import('../stores/settings')
const { checkAppUpdate, resetUpdates, useUpdates } = await import('../stores/updates')
const { handle } = await import('../stores/start')
const { onEvent } = await import('../api')
onEvent(handle)

const settle = () => act(() => new Promise<void>((r) => setTimeout(r, 0)))
const send = async (event: BackendEvent) => {
  await act(async () => window.mediaDownloaderEvent?.(event))
  await settle()
}

const SETTINGS: Settings = {
  downloadDir: 'C:\\Users\\someone\\Downloads',
  maxConcurrent: 3,
  onDuplicate: 'rename',
  format: 'mp3',
  mp3Bitrate: 320,
  mp4Height: 1080,
  language: 'en',
}
const ABOUT: AboutInfo = {
  appVersion: '0.1.0',
  components: [
    { name: 'yt-dlp', license: 'Unlicense', version: '2026.10.26' },
    { name: 'FFmpeg', license: 'GPL-3.0-or-later', version: 'N-128757-g4b42530309-20261110' },
    { name: 'Deno', license: 'MIT', version: '2.9.8' },
    { name: 'Noto Sans TC', license: 'OFL-1.1' },
    { name: 'Bricolage Grotesque', license: 'OFL-1.1' },
  ],
}

const nav = (name: string) =>
  within(screen.getByRole('navigation')).getByRole('button', { name: new RegExp(`^${name}`) })
const page = () => screen.getByRole('heading', { level: 1, name: 'Settings' }).closest('main')!
const inPage = () => within(page())
const reply = (settings: Partial<Settings>) => ({ ok: true, data: { ...SETTINGS, ...settings } })

const checked = (el: HTMLElement) => (el as HTMLInputElement).checked
const valueOf = (el: HTMLElement) => (el as HTMLSelectElement).value
/** aria-describedby, read the way a screen reader joins it. */
const description = (el: HTMLElement) =>
  (el.getAttribute('aria-describedby') ?? '').split(' ').map((id) => document.getElementById(id)?.textContent).join(' ')
const click = async (el: HTMLElement) => {
  fireEvent.click(el)
  await settle()
}
const change = async (el: HTMLElement, value: string) => {
  fireEvent.change(el, { target: { value } })
  await settle()
}

async function openSettings() {
  render(<App />)
  fireEvent.click(nav('Settings'))
  await settle()
}

beforeEach(async () => {
  for (const fn of Object.values(py)) fn.mockReset().mockResolvedValue({ ok: true })
  py.get_about.mockResolvedValue({ ok: true, data: ABOUT })
  // Like the backend, it keeps every change made so far.
  let saved = SETTINGS
  py.update_settings.mockImplementation(async (changes: Partial<Settings>) => {
    saved = { ...saved, ...changes }
    return { ok: true, data: saved }
  })
  py.list_history.mockResolvedValue({ ok: true, data: [] })
  await i18n.changeLanguage('en')
  resetQueue()
  loadQueue([])
  resetPreview()
  resetUpdates()
  setSettings(SETTINGS)
  useSettings.setState({ folderFailed: false })
  usePage.setState({ page: 'downloads', urlFocus: 0 })
  useNotices.setState({ toast: undefined, spoken: [] })
})

afterEach(cleanup)

// ---- every setting

test('each setting sends just its own change, and the page shows it at once', async () => {
  await openSettings()
  const p = inPage()
  await click(p.getByRole('radio', { name: '5' }))
  expect(py.update_settings).toHaveBeenLastCalledWith({ maxConcurrent: 5 })
  await click(p.getByRole('radio', { name: 'Skip' }))
  expect(py.update_settings).toHaveBeenLastCalledWith({ onDuplicate: 'skip' })
  await click(p.getByRole('radio', { name: 'MP4' }))
  expect(py.update_settings).toHaveBeenLastCalledWith({ format: 'mp4' })
  await change(p.getByLabelText('MP3 quality'), '192')
  expect(py.update_settings).toHaveBeenLastCalledWith({ mp3Bitrate: 192 })
  await change(p.getByLabelText('MP4 quality'), '720')
  expect(py.update_settings).toHaveBeenLastCalledWith({ mp4Height: 720 })
  await settle()
  expect(checked(p.getByRole('radio', { name: '5' }))).toBe(true)
  expect(checked(p.getByRole('radio', { name: 'Skip' }))).toBe(true)
  expect(valueOf(p.getByLabelText('MP3 quality'))).toBe('192')
  expect(valueOf(p.getByLabelText('MP4 quality'))).toBe('720')
})

test('overwrite shows the brick-red warning, tied to the choice', async () => {
  await openSettings()
  expect(screen.queryByText("The existing file will be replaced and can't be recovered.")).toBeNull()
  await click(inPage().getByRole('radio', { name: 'Overwrite' }))
  await settle()
  const warning = screen.getByText("The existing file will be replaced and can't be recovered.")
  expect(warning.classList.contains('text-danger')).toBe(true)
  expect(description(inPage().getByRole('radiogroup', { name: 'If the file already exists' }))).toBe(warning.textContent!)
})

test('settingsChanged from elsewhere (a format remembered by the main screen) moves the controls', async () => {
  await openSettings()
  await send({ type: 'settingsChanged', settings: { ...SETTINGS, format: 'mp4', mp4Height: 480, maxConcurrent: 1 } })
  const p = inPage()
  expect(checked(p.getByRole('radio', { name: 'MP4' }))).toBe(true)
  expect(valueOf(p.getByLabelText('MP4 quality'))).toBe('480')
  expect(checked(p.getByRole('radio', { name: '1' }))).toBe(true)
})

test('a default format changed here moves a preview nobody touched, not one somebody did (4b D7)', async () => {
  await openSettings()
  usePreview.setState({ touched: false })
  await click(inPage().getByRole('radio', { name: 'MP4' }))
  await send({ type: 'settingsChanged', settings: { ...SETTINGS, format: 'mp4' } })
  expect(usePreview.getState().choice.format).toBe('mp4')
  usePreview.setState({ touched: true, choice: { format: 'mp3', mp3Bitrate: 128, mp4Height: 1080 } })
  await send({ type: 'settingsChanged', settings: { ...SETTINGS, format: 'mp4' } })
  expect(usePreview.getState().choice.format).toBe('mp3')
})

test('a change the backend refuses goes back to what the backend has', async () => {
  await openSettings()
  py.update_settings.mockResolvedValue({ ok: false, error: 'unknown' })
  py.get_settings.mockResolvedValue({ ok: true, data: SETTINGS })
  await click(inPage().getByRole('radio', { name: '2' }))
  await settle()
  expect(checked(inPage().getByRole('radio', { name: '3' }))).toBe(true)
})

// ---- the download folder

test('a folder picked shows its path; with unfinished items a toast says they keep the old folder', async () => {
  loadQueue([{ id: 't1', url: 'https://youtu.be/a', format: 'mp3', quality: 320, status: 'downloading' } as QueueItem])
  await openSettings()
  py.choose_download_folder.mockResolvedValue(reply({ downloadDir: 'D:\\Music' }))
  await click(inPage().getByRole('button', { name: 'Change…' }))
  await settle()
  expect(description(inPage().getByRole('button', { name: 'Change…' }))).toBe('Download folder D:\\Music')
  expect(useNotices.getState().toast).toMatchObject({ key: 'settings.keptOldFolder', params: { count: 1 } })
})

test('cancel changes nothing and says nothing', async () => {
  await openSettings()
  py.choose_download_folder.mockResolvedValue(reply({}))
  await click(inPage().getByRole('button', { name: 'Change…' }))
  await settle()
  expect(useNotices.getState().toast).toBeUndefined()
  expect(screen.queryByRole('alert')).toBeNull()
  expect(description(inPage().getByRole('button', { name: 'Change…' }))).toBe(`Download folder ${SETTINGS.downloadDir}`)
})

test('a folder that cannot be written to says so under the row until the next try', async () => {
  await openSettings()
  py.choose_download_folder.mockResolvedValue({ ok: false, error: 'unknown' })
  await click(inPage().getByRole('button', { name: 'Change…' }))
  await settle()
  expect(screen.getByRole('alert').textContent).toContain("This folder can't be written to. Choose another folder.")
  // Not the generic error (contract 3.4).
  expect(screen.queryByText('Something unexpected went wrong')).toBeNull()
  py.choose_download_folder.mockResolvedValue(reply({}))
  await click(inPage().getByRole('button', { name: 'Change…' }))
  await settle()
  expect(screen.queryByRole('alert')).toBeNull()
})

// ---- a newer app

test('a newer app: a dot on Settings and a line with Get the update; no dialog', async () => {
  py.check_app_update.mockResolvedValue({ ok: true, data: { currentVersion: '0.1.0', latestVersion: '0.2.0' } })
  await checkAppUpdate()
  await openSettings()
  expect(within(nav('Settings')).getByRole('img', { name: 'Update available' })).toBeTruthy()
  expect(inPage().getByText('Version 0.2.0 is available')).toBeTruthy()
  await click(inPage().getByRole('button', { name: 'Get the update' }))
  expect(py.open_link).toHaveBeenCalledWith('releasePage')
  expect(document.querySelector('dialog[open]')).toBeNull()
  // A state, not a notice: still there after looking at the page (decisions/0016).
  fireEvent.click(nav('Downloads'))
  expect(within(nav('Settings')).getByRole('img', { name: 'Update available' })).toBeTruthy()
})

test.each([
  ['no newer version', { ok: true, data: { currentVersion: '0.1.0' } }],
  ['the check could not answer', { ok: false, error: 'unknown' }],
])('%s: no dot, no line, no error', async (_, answer) => {
  py.check_app_update.mockResolvedValue(answer)
  await checkAppUpdate()
  await openSettings()
  expect(within(nav('Settings')).queryByRole('img')).toBeNull()
  expect(inPage().queryByRole('button', { name: 'Get the update' })).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
})

// ---- versions and yt-dlp

test('the versions are read once, the first time the screen shows', async () => {
  render(<App />)
  await settle()
  expect(py.get_about).not.toHaveBeenCalled()
  fireEvent.click(nav('Settings'))
  await settle()
  fireEvent.click(nav('History'))
  fireEvent.click(nav('Settings'))
  await settle()
  expect(py.get_about).toHaveBeenCalledTimes(1)
  const table = within(inPage().getByRole('table'))
  expect(table.getByRole('row', { name: /FFmpeg GPL-3.0-or-later N-128757/ })).toBeTruthy()
  expect(table.getByRole('row', { name: 'Noto Sans TC OFL-1.1' })).toBeTruthy()
  expect(inPage().getByText('0.1.0, MIT License')).toBeTruthy()
})

async function checkYtDlp(answer: unknown) {
  await openSettings()
  let answerNow!: (value: unknown) => void
  py.update_engine.mockReturnValue(new Promise((r) => (answerNow = r)))
  const button = inPage().getByRole('button', { name: 'Check for updates' })
  button.focus()
  await click(button)
  await settle()
  // Checking: the button keeps focus, says so, and does nothing when pressed again.
  expect(button.textContent).toContain('Checking…')
  expect(button.getAttribute('aria-disabled')).toBe('true')
  expect(document.activeElement).toBe(button)
  expect(inPage().getByText('This can take about 20 seconds.')).toBeTruthy()
  await click(button)
  expect(py.update_engine).toHaveBeenCalledTimes(1)
  await act(async () => answerNow(answer))
  await settle()
  return button
}

test('yt-dlp already up to date', async () => {
  const button = await checkYtDlp({ ok: true, data: { updated: false, version: '2026.10.26' } })
  expect(inPage().getByText('Up to date')).toBeTruthy()
  expect(button.textContent).toContain('Check for updates')
  expect(py.get_about).toHaveBeenCalledTimes(1)
})

test('yt-dlp updated: the new version shows and the versions are read again', async () => {
  py.get_about.mockResolvedValueOnce({ ok: true, data: ABOUT }).mockResolvedValue({
    ok: true,
    data: { ...ABOUT, components: [{ name: 'yt-dlp', license: 'Unlicense', version: '2026.11.14' }, ...ABOUT.components.slice(1)] },
  })
  await checkYtDlp({ ok: true, data: { updated: true, version: '2026.11.14' } })
  expect(inPage().getByText('Updated to 2026.11.14')).toBeTruthy()
  expect(py.get_about).toHaveBeenCalledTimes(2)
  expect(within(inPage().getByRole('table')).getByRole('row', { name: /^yt-dlp Unlicense 2026.11.14$/ })).toBeTruthy()
})

test('yt-dlp network failure: the network message and Retry', async () => {
  const button = await checkYtDlp({ ok: false, error: 'network' })
  expect(inPage().getByText("Couldn't check for updates. Check your internet connection, then retry.")).toBeTruthy()
  expect(button.textContent).toContain('Retry')
  expect(inPage().queryByRole('button', { name: 'Open log file' })).toBeNull()
})

test('yt-dlp unknown failure: its own message, Retry and the log file', async () => {
  const button = await checkYtDlp({ ok: false, error: 'unknown' })
  expect(inPage().getByText("Couldn't update yt-dlp. You can retry. The log file has details.")).toBeTruthy()
  expect(button.textContent).toContain('Retry')
  await click(inPage().getByRole('button', { name: 'Open log file' }))
  expect(py.open_log_file).toHaveBeenCalled()
  py.update_engine.mockResolvedValue({ ok: true, data: { updated: false, version: '2026.10.26' } })
  await click(button)
  await settle()
  expect(inPage().getByText('Up to date')).toBeTruthy()
})

test('About opens the source code and the log folder', async () => {
  await openSettings()
  await click(inPage().getByRole('button', { name: 'Source code' }))
  await click(inPage().getByRole('button', { name: 'Open log folder' }))
  expect(py.open_link).toHaveBeenCalledWith('sourceCode')
  expect(py.open_log_folder).toHaveBeenCalled()
})

// ---- language

test('switching the language changes every screen, <html lang> and the dates', async () => {
  await openSettings()
  await change(inPage().getByLabelText('Language'), 'zh-TW')
  expect(py.update_settings).toHaveBeenLastCalledWith({ language: 'zh-TW' })
  await settle()
  expect(document.documentElement.lang).toBe('zh-TW')
  expect(screen.getByRole('heading', { level: 1, name: '設定' })).toBeTruthy()
  // The hidden screens too: their headings are in the page, just not shown.
  expect(document.getElementById('history-title')?.textContent).toContain('歷史紀錄')
  expect(within(screen.getByRole('navigation')).getByRole('button', { name: /^下載/ })).toBeTruthy()
  // Each language is named in its own words, and marked so a screen reader speaks it that way.
  const language = screen.getByLabelText('語言')
  expect(within(language).getByRole('option', { name: 'English' }).getAttribute('lang')).toBe('en')
  expect(within(language).getByRole('option', { name: '繁體中文' }).getAttribute('lang')).toBe('zh-TW')
  await change(language, 'system')
  expect(py.update_settings).toHaveBeenLastCalledWith({ language: 'system' })
})

// ---- keyboard

test('Tab goes nav, then the screen in order; radios are one stop per group', async () => {
  py.check_app_update.mockResolvedValue({ ok: true, data: { currentVersion: '0.1.0', latestVersion: '0.2.0' } })
  await checkAppUpdate()
  await openSettings()
  // A radio group is one Tab stop at its checked radio; the browser moves within it by arrow keys.
  const reachable = [...document.querySelectorAll<HTMLElement>('button, input, select')].filter(
    (el) => !el.closest('[hidden], dialog:not([open])') && !(el instanceof HTMLInputElement && el.type === 'radio' && !el.checked),
  )
  expect(reachable.map((el) => el.getAttribute('aria-label') ?? el.textContent ?? el.id)).toEqual([
    expect.stringMatching(/^Downloads/),
    'History',
    expect.stringMatching(/^Settings/),
    'Change…',
    '', // simultaneous downloads, the checked radio
    '', // if the file already exists
    '', // format
    expect.stringContaining('kbps'),
    expect.stringContaining('Up to'),
    expect.stringContaining('Match system'),
    'Get the update',
    'Check for updates',
    'Source code',
    'Open log folder',
  ])
  // Arrow keys move within a group only when its radios share one name, unlike other groups'.
  const names = screen.getAllByRole('radiogroup').map((g) => new Set([...g.querySelectorAll('input')].map((i) => i.name)))
  expect(names.every((set) => set.size === 1)).toBe(true)
  expect(new Set(names.map((set) => [...set][0])).size).toBe(names.length)
})

test('the dot and the page say nothing until the settings arrive', async () => {
  useSettings.setState({ settings: undefined })
  await openSettings()
  expect(inPage().queryByRole('button', { name: 'Change…' })).toBeNull()
  expect(useUpdates.getState().latestVersion).toBeUndefined()
})
