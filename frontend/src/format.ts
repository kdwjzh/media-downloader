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
