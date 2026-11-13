// Dev-only strip for the stage 2 sample; goes away with the rest of src/mock.
// Its labels are deliberately not in the language files: users never see it.

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { type PreviewKey, type QueueKey, previews, queues } from './sample'

interface Props {
  preview: PreviewKey
  queue: QueueKey
  onPreview: (key: PreviewKey) => void
  onQueue: (key: QueueKey) => void
  children?: ReactNode
}

const field = 'flex items-center gap-1'
const select = 'h-6 rounded border border-border bg-surface px-1'

export function StateSwitcher({ preview, queue, onPreview, onQueue, children }: Props) {
  const { i18n } = useTranslation()
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-b border-dashed border-border px-3 py-1 text-xs text-text-muted">
      <strong>Mock</strong>
      <label className={field}>
        Preview
        <select className={select} value={preview} onChange={(e) => onPreview(e.target.value as PreviewKey)}>
          {Object.keys(previews).map((key) => (
            <option key={key}>{key}</option>
          ))}
        </select>
      </label>
      <label className={field}>
        Queue
        <select className={select} value={queue} onChange={(e) => onQueue(e.target.value as QueueKey)}>
          {Object.keys(queues).map((key) => (
            <option key={key}>{key}</option>
          ))}
        </select>
      </label>
      <label className={field}>
        Language
        <select className={select} value={i18n.language} onChange={(e) => void i18n.changeLanguage(e.target.value)}>
          <option>zh-TW</option>
          <option>en</option>
        </select>
      </label>
      <span className="ml-auto">{children}</span>
    </div>
  )
}
