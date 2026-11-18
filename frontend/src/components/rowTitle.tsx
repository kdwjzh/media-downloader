import { type FocusEvent, type ReactNode, useEffect, useState } from 'react'

/** A list row's title line. Keyboard users never see the title attribute: while focus is in
 *  a row whose title is cut off, the full title lies over the text column instead (design
 *  step 5). A failed queue row's error can be cut off the same way (`[data-detail]`, two
 *  lines): only then does the overlay add `detail` under the title. Spread `rowProps` on the <li>. */
export function useRowTitle(title: string, detail?: ReactNode) {
  // What is cut off right now, and where the text column is: the overlay repeats only that.
  const [shown, setShown] = useState<{ detail: boolean; at: DOMRect }>()
  const rowProps = {
    onFocus: (e: FocusEvent<HTMLElement>) => {
      const p = e.currentTarget.querySelector('[data-title]')
      const d = e.currentTarget.querySelector('[data-detail]')
      const column = p?.parentElement
      // A control inside the text column (the log link) would end up under the overlay.
      if (!p || !column || column.contains(e.target)) return setShown(undefined)
      const titleCut = p.scrollWidth > p.clientWidth
      const detailCut = !!d && d.scrollHeight > d.clientHeight
      setShown(titleCut || detailCut ? { detail: detailCut, at: column.getBoundingClientRect() } : undefined)
    },
    onBlur: (e: FocusEvent<HTMLElement>) => {
      if (!e.currentTarget.contains(e.relatedTarget)) setShown(undefined)
    },
  }
  useEffect(() => {
    if (!shown) return
    // Fixed to where the row was: a scroll anywhere (capture) would leave it behind.
    const hide = () => setShown(undefined)
    window.addEventListener('scroll', hide, true)
    window.addEventListener('resize', hide)
    return () => {
      window.removeEventListener('scroll', hide, true)
      window.removeEventListener('resize', hide)
    }
  }, [shown])
  const titleLine = (
    <>
      <p data-title className="truncate font-medium" title={title}>
        {title}
      </p>
      {shown && (
        // Fixed, so the list's own scrolling box cannot clip it when it is taller than the row.
        <div
          aria-hidden="true"
          style={{ top: shown.at.top, left: shown.at.left - 4, width: shown.at.width + 8 }}
          className="fixed z-20 rounded-lg border border-border bg-surface px-1 wrap-anywhere"
        >
          <p className="line-clamp-3 font-medium">{title}</p>
          {shown.detail && detail && <p className="text-xs">{detail}</p>}
        </div>
      )}
    </>
  )
  return { rowProps, titleLine }
}
