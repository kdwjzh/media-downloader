const KB = 1024
const MB = KB * 1024
const GB = MB * 1024

export function formatBytes(bytes: number): string {
  if (bytes >= GB) return `${(bytes / GB).toFixed(1)} GB`
  if (bytes >= 100 * MB) return `${Math.round(bytes / MB)} MB`
  if (bytes >= MB) return `${(bytes / MB).toFixed(1)} MB`
  return `${Math.round(bytes / KB)} KB`
}

export function formatDuration(totalSec: number): string {
  const sec = Math.floor(totalSec)
  const ss = String(sec % 60).padStart(2, '0')
  const m = Math.floor(sec / 60) % 60
  const h = Math.floor(sec / 3600)
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** A finished-at time (ISO 8601, UTC) as local time, the way the interface language writes it. */
export function formatTime(iso: string, language: string): string {
  return new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
}

/** A Windows path that does not fit loses its middle folders, keeping the drive and as many
 *  of the last ones as fit; the last resort is the last folder alone. */
export function shortenPath(path: string, fits: (text: string) => boolean): string {
  const parts = path.split('\\')
  const tries = [path]
  for (let keep = parts.length - 2; keep >= 1; keep--) tries.push(`${parts[0]}\\…\\${parts.slice(-keep).join('\\')}`)
  tries.push(`…\\${parts.at(-1)}`)
  return tries.find(fits) ?? tries.at(-1)!
}
