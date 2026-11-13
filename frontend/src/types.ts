// Shapes the UI renders. Stage 4 fills them from the bridge instead of src/mock.

export type Format = 'mp3' | 'mp4'

export const MP3_BITRATES = [128, 192, 320] as const

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
  | 'network'
  | 'unknown'

// Only these get a Retry button; retrying the others cannot succeed.
export const RETRYABLE: ReadonlySet<ErrorCode> = new Set(['network', 'unknown'])

export interface MediaInfo {
  url: string
  title: string
  channel?: string
  durationSec: number
  /** Heights this video really has, short side for vertical videos. */
  heights: number[]
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
  status: TaskStatus
  percent?: number
  doneBytes?: number
  totalBytes?: number
  speedBps?: number
  etaSec?: number
  attempt?: number
  sizeBytes?: number
  error?: ErrorCode
}
