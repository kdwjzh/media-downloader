import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { confirmClose, onCloseRequested } from '../api'
import { FINISHED, useQueue } from '../stores/queue'
import { Button } from './Button'

/** Asks before closing the window while tasks are unfinished.
 *  Mounted outside the page's error boundary. If this one breaks too, it stops listening,
 *  and api/ closes the window by itself when nobody listens: the window always closes. */
export function ConfirmCloseDialog() {
  const { t } = useTranslation()
  const id = useId()
  const ref = useRef<HTMLDialogElement>(null)
  const keep = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const count = useQueue((s) => s.items.filter((item) => !FINISHED.has(item.status)).length)

  useEffect(
    () =>
      onCloseRequested(() => {
        // The last task may have finished as the close button was pressed: nothing to ask.
        const unfinished = useQueue.getState().items.some((item) => !FINISHED.has(item.status))
        if (unfinished) setOpen(true)
        else void confirmClose()
      }),
    [],
  )

  useEffect(() => {
    const dialog = ref.current
    // showModal() traps focus, makes Esc cancel, and gives focus back when it closes.
    if (open && !dialog?.open) {
      dialog?.showModal()
      keep.current?.focus() // the safe answer has focus, as in every confirmation (MASTER)
    }
    if (!open && dialog?.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-body`}
      onClose={() => setOpen(false)}
      className="m-auto w-[min(440px,calc(100vw-48px))] animate-fade-in rounded-[10px] bg-surface p-6 text-text backdrop:bg-scrim motion-reduce:animate-none"
    >
      <h2 id={`${id}-title`} className="text-base font-medium">
        {t('close.title', { count })}
      </h2>
      <p id={`${id}-body`} className="mt-2 text-text-muted">
        {t('close.body')}
      </p>
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button ref={keep} onClick={() => setOpen(false)}>
          {t('close.keep')}
        </Button>
        <Button variant="danger" onClick={() => void confirmClose()}>
          {t('close.confirm')}
        </Button>
      </div>
    </dialog>
  )
}
