// Shapes the UI renders, as agreed in docs/介面與後端的約定.md.
// Stage 4 fills them from the bridge instead of src/mock.

export type Format = 'mp3' | 'mp4'

export const MP3_BITRATES = [128, 192, 320] as const

// Simultaneous downloads the settings page offers; must match the backend's MAX_CONCURRENT.
export const CONCURRENT_CHOICES = [1, 2, 3, 4, 5] as const

// Keys of `error.*` in the language files; must match the backend's ErrorCode.
export type ErrorCode =
  | 'invalidUrl'
  | 'unsupportedSite'
  | 'notFound'
  | 'private'
  | 'ageRestricted'
  | 'membersOnly'
  | 'geoBlocked'
  | 'playlistNotFound'
  | 'liveNotSupported'
  | 'playlistUrl'
  | 'network'
  | 'unknown'

// Only these get a Retry button; retrying the others cannot succeed.
export const RETRYABLE: ReadonlySet<ErrorCode> = new Set(['network', 'unknown'])

/** One selectable format and quality. MP3: kbps. MP4: height, short side for vertical videos. */
export interface FormatOption {
  format: Format
  quality: number
  /** Estimated by the backend; absent when the source gives no size. */
  sizeBytes?: number
}

export interface MediaInfo {
  url: string
  title: string
  channel?: string
  durationSec: number
  platform: string
  /** Everything this video offers: the three MP3 bitrates and the heights it really has. */
  options: FormatOption[]
  thumb?: string
}

export type Preview =
  | { kind: 'loading'; url: string }
  | { kind: 'ready'; info: MediaInfo }
  | { kind: 'error'; url: string; code: ErrorCode }

export type TaskStatus =
  | 'queued'
  | 'fetching'
  | 'downloading'
  | 'retrying'
  | 'converting'
  | 'merging'
  | 'done'
  | 'failed'
  | 'cancelled'

export interface QueueItem {
  id: string
  url: string
  title?: string
  thumb?: string
  format: Format
  quality: number
  status: TaskStatus
  percent?: number
  doneBytes?: number
  totalBytes?: number
  speedBps?: number
  etaSec?: number
  attempt?: number
  sizeBytes?: number
  /** Done without downloading: the file already existed and duplicates are skipped. */
  skipped?: boolean
  error?: ErrorCode
}
