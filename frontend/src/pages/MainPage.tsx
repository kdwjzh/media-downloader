import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/Button'
import { PreviewPanel } from '../components/PreviewPanel'
import { QueueRow } from '../components/QueueRow'
import type { Format, Preview, QueueItem } from '../types'

const FINISHED: ReadonlySet<QueueItem['status']> = new Set(['done', 'failed', 'cancelled'])

interface Props {
  preview: Preview | null
  queue: QueueItem[]
  defaults: { format: Format; bitrate: number; height: number }
}

function EmptyState() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
      {/* Three stacked sleeves, drawn with CSS. Decorative and static. */}
      <div aria-hidden="true" className="relative mb-4 h-20 w-28">
        <div className="absolute top-2 left-0 size-16 -rotate-6 rounded-md bg-accent-soft" />
        <div className="absolute top-0 left-6 size-16 rotate-3 rounded-md bg-highlight" />
        <div className="absolute top-3 left-12 size-16 rounded-md bg-accent" />
      </div>
      <h2 className="text-base font-medium">{t('empty.title')}</h2>
      <p className="max-w-md text-text-muted">{t('empty.body')}</p>
    </div>
  )
}

export function MainPage({ preview, queue, defaults }: Props) {
  const { t } = useTranslation()
  const urlId = useId()
  const [url, setUrl] = useState('')

  return (
    <main className="flex min-w-0 flex-1 flex-col gap-4 p-6 pl-2">
      <h1 className="sr-only">{t('nav.downloads')}</h1>
      <form className="flex flex-col gap-1" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor={urlId} className="font-medium">
          {t('url.label')}
        </label>
        <div className="flex gap-2">
          <input
            id={urlId}
            type="url"
            autoComplete="off"
            spellCheck={false}
            placeholder={t('url.placeholder')}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="h-9 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 placeholder:text-text-muted"
          />
          <Button type="submit" className="h-9" disabled={url.trim() === ''}>
            {t('url.lookUp')}
          </Button>
        </div>
      </form>

      {preview && <PreviewPanel preview={preview} defaults={defaults} />}

      {queue.length === 0 && !preview ? (
        <EmptyState />
      ) : (
        <section className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="flex h-8 items-center justify-between">
            <h2 className="font-medium">{t('queue.title', { count: queue.length })}</h2>
            {queue.some((item) => FINISHED.has(item.status)) && (
              <Button variant="text">{t('queue.clearFinished')}</Button>
            )}
          </div>
          {queue.length === 0 ? (
            <p className="text-text-muted">{t('queue.emptyInline')}</p>
          ) : (
            <ul className="min-h-0 divide-y divide-divider overflow-y-auto rounded-[10px] bg-surface">
              {queue.map((item) => (
                <QueueRow key={item.id} item={item} />
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  )
}
