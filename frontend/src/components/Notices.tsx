import { Info } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { type Notice, hideToast, useNotices } from '../stores/notices'

export const TOAST_MS = 5000

function useText() {
  const { t } = useTranslation()
  // A `reason` param is itself a key (the error title of a failed task).
  return ({ key, params }: Notice): string => {
    const options: Record<string, unknown> = { ...params }
    if (params?.reason) options.reason = t(String(params.reason))
    return t(key, options)
  }
}

/** Polite: screen readers finish what they are saying first. Nothing visible. */
export function LiveRegion() {
  const spoken = useNotices((s) => s.spoken)
  const text = useText()
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {spoken.map((n) => (
        <p key={n.id}>{text(n)}</p>
      ))}
    </div>
  )
}

/** One short message over the bottom of the main area; it goes after TOAST_MS, and waits
 *  while the pointer rests on it (MASTER: toast). */
export function Toast() {
  const toast = useNotices((s) => s.toast)
  const text = useText()
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    if (!toast || paused) return
    const timer = setTimeout(() => hideToast(toast.id), TOAST_MS)
    return () => clearTimeout(timer)
  }, [toast, paused])

  return (
    // The status role stays in the page so a new message is read out when it appears.
    <div role="status" className="pointer-events-none fixed right-0 bottom-4 left-22 z-20 flex justify-center px-6">
      {toast && (
        <p
          key={toast.id}
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
          className="pointer-events-auto flex animate-fade-in items-center gap-2 rounded-lg bg-text px-3 py-2 text-on-accent motion-reduce:animate-none"
        >
          <Info size={16} aria-hidden="true" className="shrink-0" />
          {text(toast)}
        </p>
      )}
    </div>
  )
}
