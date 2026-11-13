// Mock data for the stage 2 static sample. Stage 4 deletes src/mock and feeds the
// same shapes (src/types.ts) from the bridge.
// Titles, durations and sizes come from docs/介面設計依據.md section 6.
// Thumbnails are flat colours: real ones would mean a network fetch or copying
// someone else's image into the repo.

import type { Format, MediaInfo, Preview, QueueItem } from '../types'

const MB = 1024 * 1024
const WATCH = 'https://www.youtube.com/watch?v='

const poem: MediaInfo = {
  url: `${WATCH}sample-poem`,
  title: '公視新創電影《最後的詩句》30秒搶先看！',
  channel: '公視戲劇 PTS Drama',
  durationSec: 42,
  heights: [144, 240, 360, 480, 720, 1080],
  thumb: '#7a5c6e',
}

const resolutionTest: MediaInfo = {
  url: `${WATCH}sample-4k`,
  title: '4K 2K 1080p 720p 480p video resolution test',
  durationSec: 11,
  heights: [144, 240, 360, 480, 720, 1080, 1440, 2160],
  thumb: '#3f6f7a',
}

// Made-up estimates; 144p is null to show the "size unknown" case.
const mp4Sizes: Record<string, Record<number, number | null>> = {
  [poem.url]: { 144: null, 240: 0.9 * MB, 360: 1.4 * MB, 480: 2.1 * MB, 720: 3.9 * MB, 1080: 6.6 * MB },
  [resolutionTest.url]: {
    144: 0.2 * MB,
    240: 0.3 * MB,
    360: 0.5 * MB,
    480: 0.8 * MB,
    720: 1.6 * MB,
    1080: 3.4 * MB,
    1440: 7.9 * MB,
    2160: 18 * MB,
  },
}

/** MP3 size is bitrate x duration, the only estimate yt-dlp allows; MP4 is a lookup. */
export function estimateSize(info: MediaInfo, format: Format, quality: number): number | null {
  if (format === 'mp3') return (quality * 1000 * info.durationSec) / 8
  return mp4Sizes[info.url]?.[quality] ?? null
}

export const previews = {
  none: null,
  loading: { kind: 'loading', url: `${WATCH}jNQXAC9IVRw` },
  ready: { kind: 'ready', info: poem },
  ready4k: { kind: 'ready', info: resolutionTest },
  errorPrivate: { kind: 'error', url: `${WATCH}sample-private`, code: 'private' },
  errorNetwork: { kind: 'error', url: `${WATCH}sample-offline`, code: 'network' },
  errorUnknown: { kind: 'error', url: `${WATCH}sample-unknown`, code: 'unknown' },
  errorLive: { kind: 'error', url: `${WATCH}sample-live`, code: 'liveNotSupported' },
} satisfies Record<string, Preview | null>

const sixStates: QueueItem[] = [
  {
    id: 'q1',
    url: `${WATCH}sample-noise`,
    title: 'White Noise 1 Hour Long',
    thumb: '#8d8a94',
    format: 'mp3',
    status: 'queued',
  },
  {
    id: 'q2',
    url: `${WATCH}sample-big`,
    title: '5 分鐘的 4K 影片（大檔案樣本）',
    thumb: '#3f6f7a',
    format: 'mp4',
    status: 'downloading',
    percent: 62,
    doneBytes: 599 * MB,
    totalBytes: 966 * MB,
    speedBps: 8.4 * MB,
    etaSec: 44,
  },
  {
    id: 'q3',
    url: `${WATCH}sample-daidai`,
    title: 'Shakira, Burna Boy - Dai Dai (Official Video)',
    thumb: '#b5654a',
    format: 'mp3',
    status: 'converting',
  },
  {
    id: 'q4',
    url: poem.url,
    title: poem.title,
    thumb: poem.thumb,
    format: 'mp3',
    status: 'done',
    sizeBytes: 1.6 * MB,
  },
  {
    id: 'q5',
    url: resolutionTest.url,
    title: resolutionTest.title,
    thumb: resolutionTest.thumb,
    format: 'mp4',
    status: 'failed',
    error: 'network',
  },
  {
    id: 'q6',
    url: `${WATCH}jNQXAC9IVRw`,
    title: 'Me at the zoo',
    thumb: '#6f8a5c',
    format: 'mp3',
    status: 'cancelled',
  },
]

const otherStates: QueueItem[] = [
  { id: 'o1', url: `${WATCH}sample-requeued-from-history`, format: 'mp3', status: 'fetching' },
  {
    id: 'o2',
    url: `${WATCH}sample-noise`,
    title: 'White Noise 1 Hour Long',
    thumb: '#8d8a94',
    format: 'mp3',
    status: 'retrying',
    percent: 31,
    attempt: 2,
  },
  {
    id: 'o3',
    url: `${WATCH}sample-vertical`,
    title: '直式影片樣本（1080x1920，51 秒）',
    thumb: '#5c6f8a',
    format: 'mp4',
    status: 'merging',
  },
  {
    id: 'o4',
    url: `${WATCH}sample-big`,
    title: '5 分鐘的 4K 影片（大檔案樣本）',
    thumb: '#3f6f7a',
    format: 'mp4',
    // No total size: the row drops "/ total" and the time left.
    status: 'downloading',
    percent: 12,
    doneBytes: 118 * MB,
    speedBps: 2.1 * MB,
  },
  {
    id: 'o5',
    url: `${WATCH}sample-private`,
    title: 'Shakira, Burna Boy - Dai Dai (Official Video)',
    thumb: '#b5654a',
    format: 'mp3',
    status: 'failed',
    error: 'private',
  },
  {
    id: 'o6',
    url: `${WATCH}sample-unknown`,
    title: 'Me at the zoo',
    thumb: '#6f8a5c',
    format: 'mp3',
    status: 'failed',
    error: 'unknown',
  },
]

export const queues = {
  empty: [],
  sixStates,
  otherStates,
} satisfies Record<string, QueueItem[]>

export type PreviewKey = keyof typeof previews
export type QueueKey = keyof typeof queues
