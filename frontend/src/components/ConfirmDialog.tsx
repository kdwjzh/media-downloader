import { useEffect, useId, useRef } from 'react'
import { Button } from './Button'

interface Props {
  open: boolean
  title: string
  body: string
  /** The safe answer: it has focus when the dialog opens, and Esc means it too. */
  keepLabel: string
  confirmLabel: string
  onKeep: () => void
  onConfirm: () => void
}

/** A question before something that cannot be undone (MASTER: confirmation dialogs). */
export function ConfirmDialog({ open, title, body, keepLabel, confirmLabel, onKeep, onConfirm }: Props) {
  const id = useId()
  const ref = useRef<HTMLDialogElement>(null)
  const keep = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const dialog = ref.current
    // showModal() traps focus, makes Esc cancel, and gives focus back when it closes.
    if (open && !dialog?.open) {
      dialog?.showModal()
      // Opened by a mouse click, Chromium focuses it without a ring (MASTER: focus).
      // showModal() has already focused this first button, and focusing it again changes
      // nothing, so it lets go first.
      keep.current?.blur()
      keep.current?.focus({ focusVisible: true })
    }
    if (!open && dialog?.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-body`}
      onClose={() => open && onKeep()}
      className="m-auto w-[min(440px,calc(100vw-48px))] animate-fade-in rounded-[10px] bg-surface p-6 text-text backdrop:bg-scrim motion-reduce:animate-none"
    >
      <h2 id={`${id}-title`} className="text-base font-medium">
        {title}
      </h2>
      <p id={`${id}-body`} className="mt-2 text-text-muted">
        {body}
      </p>
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <Button ref={keep} onClick={onKeep}>
          {keepLabel}
        </Button>
        <Button variant="danger" onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  )
}
