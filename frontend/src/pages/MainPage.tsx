import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { PlaylistPanel } from '../components/PlaylistPanel'
import { PreviewPanel } from '../components/PreviewPanel'
import { QueueList } from '../components/QueueList'
import { Sleeves } from '../components/Sleeves'
import { isOtherTextField, looksLikeUrl } from '../paste'
import { showToast } from '../stores/notices'
import { goToUrlBox, usePage } from '../stores/page'
import { lookUp, usePreview } from '../stores/preview'
import { FINISHED, cancelAll, clearFinished, useQueue } from '../stores/queue'

function EmptyState() {
  const { t } = useTranslation()
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
      <Sleeves />
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
  const preview = usePreview((s) => s.preview)
  const queue = useQueue((s) => s.items)
  const [askCancelAll, setAskCancelAll] = useState(false)
  const unfinished = queue.filter((item) => !FINISHED.has(item.status)).length

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
      // From another screen: back here first, where the preview will show.
      if (usePage.getState().page !== 'downloads') goToUrlBox()
      submit(text)
    }
    document.addEventListener('paste', onPaste)
    return () => document.removeEventListener('paste', onPaste)
  }, [])

  // "Go to Downloads" and a paste on another screen land in the URL box.
  const urlFocus = usePage((s) => s.urlFocus)
  useEffect(() => {
    if (urlFocus > 0) urlBox.current?.focus()
  }, [urlFocus])

  const focusQueue = () => queueHeading.current?.focus()
  const focusUrl = () => urlBox.current?.focus()

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

      {preview?.kind === 'playlist' ? (
        // Replaces the preview and the queue until it is added or closed (pages/playlist.md).
        <PlaylistPanel playlist={preview.playlist} onDone={focusUrl} />
      ) : (
        <>
          <PreviewPanel onDone={focusUrl} />
          {queue.length === 0 && !preview ? (
            <EmptyState />
          ) : (
            <section className="flex min-h-0 flex-1 flex-col gap-2">
              <div className="flex h-8 items-center gap-2">
                {/* Takes focus when the row or button that had it goes away. */}
                <h2 ref={queueHeading} tabIndex={-1} className="mr-auto font-medium">
                  {t('queue.title', { count: queue.length })}
                </h2>
                {unfinished > 0 && (
                  <Button variant="text" onClick={() => setAskCancelAll(true)}>
                    {t('queue.cancelAll')}
                  </Button>
                )}
                {queue.some((item) => FINISHED.has(item.status)) && (
                  <Button variant="text" onClick={() => void clearFinished().then(focusQueue)}>
                    {t('queue.clearFinished')}
                  </Button>
                )}
              </div>
              {queue.length === 0 ? (
                <p className="text-text-muted">{t('queue.emptyInline')}</p>
              ) : (
                <QueueList items={queue} onRemoved={focusQueue} />
              )}
            </section>
          )}
        </>
      )}
      <ConfirmDialog
        open={askCancelAll}
        title={t('cancelAll.title', { count: unfinished })}
        body={t('cancelAll.body')}
        keepLabel={t('close.keep')}
        confirmLabel={t('queue.cancelAll')}
        onKeep={() => setAskCancelAll(false)}
        onConfirm={() => {
          setAskCancelAll(false)
          // The button goes away with the last unfinished task; focus has to land somewhere.
          void cancelAll().then(focusQueue)
        }}
      />
    </main>
  )
}
