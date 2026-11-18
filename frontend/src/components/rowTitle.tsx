import { type FocusEvent, type ReactNode, useEffect, useLayoutEffect, useState } from 'react'

interface Shown {
  row: HTMLElement
  detail: boolean
  top: number
  left: number
  width: number
}

/** What is cut off in the row now, and where its text column is; undefined: nothing is cut off. */
function measure(row: HTMLElement): Shown | undefined {
  const p = row.querySelector('[data-title]')
  const d = row.querySelector('[data-detail]')
  const column = p?.parentElement
  if (!p || !column) return undefined
  const titleCut = p.scrollWidth > p.clientWidth
  const detailCut = !!d && d.scrollHeight > d.clientHeight
  if (!titleCut && !detailCut) return undefined
  const at = column.getBoundingClientRect()
  return { row, detail: detailCut, top: at.top, left: at.left, width: at.width }
}

const same = (a?: Shown, b?: Shown) =>
  a?.detail === b?.detail && a?.top === b?.top && a?.left === b?.left && a?.width === b?.width

/** A list row's title line. Keyboard users never see the title attribute: while focus is in
 *  a row whose title is cut off, the full title lies over the text column instead (design
 *  step 5). A failed queue row's error can be cut off the same way (`[data-detail]`, two
 *  lines): only then does the overlay add `detail` under the title. Spread `rowProps` on the <li>. */
export function useRowTitle(title: string, detail?: ReactNode) {
  const [shown, setShown] = useState<Shown>()
  const rowProps = {
    onFocus: (e: FocusEvent<HTMLElement>) => {
      // A control inside the text column (the log link) would end up under the overlay.
      const column = e.currentTarget.querySelector('[data-title]')?.parentElement
      setShown(column?.contains(e.target) ? undefined : measure(e.currentTarget))
    },
    onBlur: (e: FocusEvent<HTMLElement>) => {
      if (!e.currentTarget.contains(e.relatedTarget)) setShown(undefined)
    },
  }
  // Focus stays in the row while its status changes the buttons, and with them the width of the
  // text column and what is cut off: measure again after every redraw while it shows.
  useLayoutEffect(() => {
    if (!shown) return
    const now = measure(shown.row)
    if (!same(now, shown)) setShown(now)
  })
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
          style={{ top: shown.top, left: shown.left - 4, width: shown.width + 8 }}
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
