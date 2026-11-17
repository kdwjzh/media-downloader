import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Format } from '../types'

// The shape tells the format: MP3 is a square cover, MP4 stays 16:9.
// The column in a list keeps the 16:9 width either way so titles line up.
const sizes = {
  row: { column: 'w-23', mp3: 'size-13', mp4: 'h-13 w-23' },
  preview: { column: '', mp3: 'size-24', mp4: 'h-[90px] w-40' },
  // The playlist's 56-high rows (pages/playlist.md).
  small: { column: 'w-[71px]', mp3: 'size-10', mp4: 'h-10 w-[71px]' },
}

interface Props {
  format: Format
  src?: string
  size?: keyof typeof sizes
  loading?: boolean
}

export function Thumb({ format, src, size = 'row', loading = false }: Props) {
  const s = sizes[size]
  const [broken, setBroken] = useState<string>()
  return (
    <div className={`${s.column} shrink-0`} aria-hidden="true">
      <div
        className={`${s[format]} overflow-hidden rounded-md bg-divider ${loading ? 'animate-skeleton motion-reduce:animate-none' : ''}`}
      >
        {/* A thumbnail that fails to load leaves the placeholder showing. */}
        {src && src !== broken && (
          <img src={src} alt="" className="size-full object-cover" onError={() => setBroken(src)} />
        )}
      </div>
    </div>
  )
}

export function FormatTag({ format }: { format: Format }) {
  const { t } = useTranslation()
  const colors = format === 'mp3' ? 'bg-highlight text-text' : 'bg-text text-on-accent'
  return (
    <span className={`rounded px-2 py-0.5 font-display text-xs font-semibold ${colors}`}>
      {t(`format.${format}`)}
    </span>
  )
}
