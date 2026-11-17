import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { confirmClose, onCloseRequested } from '../api'
import { FINISHED, useQueue } from '../stores/queue'
import { ConfirmDialog } from './ConfirmDialog'

/** Asks before closing the window while tasks are unfinished.
 *  Mounted outside the page's error boundary. If this one breaks too, it stops listening,
 *  and api/ closes the window by itself when nobody listens: the window always closes. */
export function ConfirmCloseDialog() {
  const { t } = useTranslation()
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

  return (
    <ConfirmDialog
      open={open}
      title={t('close.title', { count })}
      body={t('close.body')}
      keepLabel={t('close.keep')}
      confirmLabel={t('close.confirm')}
      onKeep={() => setOpen(false)}
      onConfirm={() => void confirmClose()}
    />
  )
}
