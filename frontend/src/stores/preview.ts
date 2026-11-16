// The preview under the URL box: what was looked up, and the format and quality chosen
// for it. Kept here, not in the component, because pasting the next URL adds this one
// with whatever is chosen right now (decisions/0006).

import { create } from 'zustand'
import * as api from '../api'
import type { Format, MediaInfo, Preview, Settings } from '../types'
import { announce } from './notices'
import { useSettings } from './settings'

export interface Choice {
  format: Format
  mp3Bitrate: number
  /** A ceiling: the video gets its best height at or under it. */
  mp4Height: number
}

interface PreviewState {
  preview: Preview | null
  choice: Choice
  /** The person changed format or quality on this preview: settingsChanged leaves it alone. */
  touched: boolean
}

// Contract Q7, until getSettings() answers.
const DEFAULT_CHOICE: Choice = { format: 'mp3', mp3Bitrate: 320, mp4Height: 1080 }

export const usePreview = create<PreviewState>(() => ({ preview: null, choice: DEFAULT_CHOICE, touched: false }))

function remembered(settings = useSettings.getState().settings): Choice {
  return settings ? { format: settings.format, mp3Bitrate: settings.mp3Bitrate, mp4Height: settings.mp4Height } : DEFAULT_CHOICE
}

// Every lookup gets a number; a reply whose number is no longer current is thrown away.
let current = 0

export function resetPreview(): void {
  current++
  usePreview.setState({ preview: null, choice: DEFAULT_CHOICE, touched: false })
}

/** Heights this video has, best first. Empty: no picture at all, MP3 only. */
export function heightsOf(info: MediaInfo): number[] {
  return info.options.filter((o) => o.format === 'mp4').map((o) => o.quality).sort((a, b) => b - a)
}

/** What "Add to queue" would send for this video with this choice. */
export function resolve(info: MediaInfo, choice: Choice): { format: Format; quality: number } {
  const heights = heightsOf(info)
  if (choice.format === 'mp3' || heights.length === 0) return { format: 'mp3', quality: choice.mp3Bitrate }
  return { format: 'mp4', quality: heights.find((h) => h <= choice.mp4Height) ?? heights.at(-1)! }
}

/** Looks a URL up. Whatever the old preview was, it is dealt with first (decisions/0006). */
export async function lookUp(text: string): Promise<void> {
  const url = text.trim()
  if (url === '') return
  const { preview, choice } = usePreview.getState()
  if (preview?.kind === 'ready') void addAuto(preview.info.url, resolve(preview.info, choice))
  if (preview?.kind === 'loading') {
    // Its options are unknown yet: the remembered height is a valid ceiling for any video.
    const format = choice.format
    void addAuto(preview.url, { format, quality: format === 'mp3' ? choice.mp3Bitrate : choice.mp4Height })
  }
  const mine = ++current
  usePreview.setState({ preview: { kind: 'loading', url }, choice: remembered(), touched: false })
  const reply = await api.lookup(url)
  if (mine !== current) return
  usePreview.setState({
    preview: !reply.ok
      ? { kind: 'error', url, code: reply.error }
      : reply.data.kind === 'video'
        ? { kind: 'ready', info: reply.data.info }
        : { kind: 'playlist', playlist: reply.data.playlist },
    // Settings may have changed while it was looking (the auto-add above remembers its format).
    choice: remembered(),
  })
}

async function addAuto(url: string, { format, quality }: { format: Format; quality: number }): Promise<void> {
  if ((await api.addToQueue([url], format, quality)).ok) announce('queue.autoAdded')
}

/** The preview's own button. True when added; a failure turns the preview into its error. */
export async function addPreview(): Promise<boolean> {
  const { preview, choice } = usePreview.getState()
  if (preview?.kind !== 'ready') return false
  const { format, quality } = resolve(preview.info, choice)
  const mine = ++current
  const reply = await api.addToQueue([preview.info.url], format, quality)
  if (mine !== current) return false
  if (!reply.ok) {
    usePreview.setState({ preview: { kind: 'error', url: preview.info.url, code: reply.error } })
    return false
  }
  usePreview.setState({ preview: null })
  announce('live.added', { title: preview.info.title })
  return true
}

/** Closing a preview still looking makes its late answer go nowhere. */
export function closePreview(): void {
  current++
  usePreview.setState({ preview: null })
}

export function choose(change: Partial<Choice>): void {
  usePreview.setState((s) => ({ choice: { ...s.choice, ...change }, touched: true }))
}

export function previewSettingsChanged(settings: Settings): void {
  if (!usePreview.getState().touched) usePreview.setState({ choice: remembered(settings) })
}
