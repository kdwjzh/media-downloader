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
  // shortcut: 4b has no playlist screen yet, so a playlist only shows its size; 4c replaces this.
  | { kind: 'playlist'; playlist: PlaylistInfo }

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

// ---- Section 5.2 F: playlists

export interface PlaylistEntry {
  url: string
  title?: string
  channel?: string
  durationSec?: number
  /** Small thumbnail URL (at most 336x188). */
  thumb?: string
  /** False: private or deleted. Then only `url` is there; the row is dimmed and cannot be ticked. */
  available: boolean
}

export interface PlaylistInfo {
  url: string
  title: string
  channel?: string
  platform: string
  entries: PlaylistEntry[]
}

export type LookupResult = { kind: 'video'; info: MediaInfo } | { kind: 'playlist'; playlist: PlaylistInfo }

// ---- G: history

export interface HistoryEntry {
  id: string
  url: string
  title: string
  format: Format
  quality: number
  sizeBytes: number
  /** ISO 8601 in UTC; show it with Intl.DateTimeFormat in local time. */
  finishedAt: string
  /** A data: URL of the small thumbnail kept on this computer. */
  thumb?: string
}

// ---- H: settings, updates, about, open, progress

export type OnDuplicate = 'skip' | 'overwrite' | 'rename'
export type Language = 'system' | 'zh-TW' | 'en'

export interface Settings {
  /** Only changes through chooseDownloadFolder(). */
  downloadDir: string
  maxConcurrent: number
  onDuplicate: OnDuplicate
  /** format, mp3Bitrate and mp4Height are the defaults and what was used last. */
  format: Format
  mp3Bitrate: number
  mp4Height: number
  language: Language
}

/** What updateSettings() may change. */
export type SettingsChanges = Partial<Omit<Settings, 'downloadDir'>>

export interface AppUpdateInfo {
  currentVersion: string
  /** Only when a newer version exists. */
  latestVersion?: string
}

export interface EngineUpdateResult {
  updated: boolean
  version: string
}

export interface Component {
  name: string
  license: string
  version?: string
}

export interface AboutInfo {
  appVersion: string
  components: Component[]
}

export interface OpenResult {
  opened: 'file' | 'folder' | 'none'
}

/** Replaces all five progress fields of the task: one that is absent has no value now. */
export interface TaskProgress {
  id: string
  percent?: number
  doneBytes: number
  totalBytes?: number
  speedBps?: number
  etaSec?: number
}

// ---- Section 4: events

export type BackendEvent =
  | { type: 'tasksChanged'; tasks: QueueItem[] }
  | { type: 'tasksRemoved'; ids: string[] }
  | { type: 'taskProgress'; progress: TaskProgress }
  | { type: 'historyAdded'; entry: HistoryEntry }
  | { type: 'settingsChanged'; settings: Settings }
  | { type: 'closeRequested' }
