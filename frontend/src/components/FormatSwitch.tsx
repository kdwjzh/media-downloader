import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import type { Format } from '../types'

const FORMATS: Format[] = ['mp3', 'mp4']

interface Props {
  value: Format
  onChange: (format: Format) => void
  /** No picture, no MP4 (contract 2.3). */
  noVideo?: boolean
  /** The label sits beside the switch instead of above it. */
  inline?: boolean
}

/** MP3 | MP4 as side-by-side radio buttons (MASTER: inputs). */
export function FormatSwitch({ value, onChange, noVideo = false, inline = false }: Props) {
  const { t } = useTranslation()
  const id = useId()
  return (
    <div className={`flex gap-1 ${inline ? 'items-center gap-2' : 'flex-col'}`}>
      <span id={id} className="text-xs whitespace-nowrap text-text-muted">
        {t('format.label')}
      </span>
      <div role="radiogroup" aria-labelledby={id} className="flex h-9 items-center rounded-lg border border-border bg-surface p-0.5">
        {FORMATS.map((f) => (
          <label key={f} className="cursor-pointer has-disabled:cursor-not-allowed has-disabled:opacity-45">
            <input
              type="radio"
              name={id}
              className="peer sr-only"
              checked={value === f}
              disabled={f === 'mp4' && noVideo}
              onChange={() => onChange(f)}
            />
            <span className="flex h-7.5 min-w-12 items-center justify-center rounded-md px-3 transition-colors duration-150 peer-checked:bg-accent peer-checked:text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent peer-not-checked:peer-enabled:hover:bg-accent-soft">
              {t(`format.${f}`)}
            </span>
          </label>
        ))}
      </div>
    </div>
  )
}
