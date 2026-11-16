import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/Button'
import { PreviewPanel } from '../components/PreviewPanel'
import { QueueRow } from '../components/QueueRow'
import { isOtherTextField, looksLikeUrl } from '../paste'
import { showToast } from '../stores/notices'
import { lookUp, usePreview } from '../stores/preview'
import { FINISHED, clearFinished, useQueue } from '../stores/queue'

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

export function MainPage() {
  const { t } = useTranslation()
  const urlId = useId()
  const [url, setUrl] = useState('')
  const urlBox = useRef<HTMLInputElement>(null)
  const queueHeading = useRef<HTMLHeadingElement>(null)
  const hasPreview = usePreview((s) => s.preview !== null)
  const queue = useQueue((s) => s.items)

  function submit(text: string) {
    setUrl('') // emptied right away, ready for the next one
    void lookUp(text)
  }

  // Ctrl+V anywhere in the window looks up what was copied (design step 6).
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      if (document.querySelector('dialog[open]')) return
      const target = document.activeElement
      if (isOtherTextField(target, urlBox.current)) return
      const text = e.clipboardData?.getData('text') ?? ''
      if (target && target === urlBox.current) {
        // A box with text in it is being edited; an empty one pastes and looks up at once.
        if ((target as HTMLInputElement).value !== '' || !looksLikeUrl(text)) return
      } else if (!looksLikeUrl(text)) {
        if (text.trim() !== '') showToast('toast.notUrl')
        return
      }
      e.preventDefault()
      submit(text)
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [])

  const focusQueue = () => queueHeading.current?.focus()

  return (
    <main className="flex min-w-0 flex-1 flex-col gap-4 p-6 pl-2">
      <h1 className="sr-only">{t('nav.downloads')}</h1>
      <form
        className="flex flex-col gap-1"
        onSubmit={(e) => {
          e.preventDefault()
          submit(url)
        }}
      >
        <label htmlFor={urlId} className="font-medium">
          {t('url.label')}
        </label>
        <div className="flex gap-2">
          <input
            id={urlId}
            ref={urlBox}
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

      <PreviewPanel onDone={() => urlBox.current?.focus()} />

      {queue.length === 0 && !hasPreview ? (
        <EmptyState />
      ) : (
        <section className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="flex h-8 items-center justify-between">
            {/* Takes focus when the row or button that had it goes away. */}
            <h2 ref={queueHeading} tabIndex={-1} className="font-medium">
              {t('queue.title', { count: queue.length })}
            </h2>
            {queue.some((item) => FINISHED.has(item.status)) && (
              <Button variant="text" onClick={() => void clearFinished().then(focusQueue)}>
                {t('queue.clearFinished')}
              </Button>
            )}
          </div>
          {queue.length === 0 ? (
            <p className="text-text-muted">{t('queue.emptyInline')}</p>
          ) : (
            <ul className="min-h-0 divide-y divide-divider overflow-y-auto rounded-[10px] bg-surface">
              {queue.map((item) => (
                <QueueRow key={item.id} item={item} onRemoved={focusQueue} />
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  )
}
