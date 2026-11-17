import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import type { Format } from '../types'
import { Segmented } from './Segmented'

interface Props {
  value: Format
  onChange: (format: Format) => void
  /** No picture, no MP4 (contract 2.3). */
  noVideo?: boolean
  /** The label sits beside the switch instead of above it. */
  inline?: boolean
}

/** MP3 | MP4 with its label (MASTER: inputs). */
export function FormatSwitch({ value, onChange, noVideo = false, inline = false }: Props) {
  const { t } = useTranslation()
  const id = useId()
  return (
    <div className={`flex gap-1 ${inline ? 'items-center gap-2' : 'flex-col'}`}>
      <span id={id} className="text-xs whitespace-nowrap text-text-muted">
        {t('format.label')}
      </span>
      <Segmented
        labelledBy={id}
        options={[
          { value: 'mp3', label: t('format.mp3') },
          { value: 'mp4', label: t('format.mp4'), disabled: noVideo },
        ]}
        value={value}
        onChange={onChange}
      />
    </div>
  )
}
