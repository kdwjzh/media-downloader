// Fixed-height lists that may run to thousands of rows (MASTER: lists over 100 rows are
// virtual). Every row has the same height, so which rows are in view is plain arithmetic.

import { type RefObject, useLayoutEffect, useState } from 'react'

/** Up to this many rows everything is drawn, as before. */
export const VIRTUAL_FROM = 100
/** Rows drawn beyond each edge of the view, so a fast scroll does not show blanks. */
const OVERSCAN = 6

/** Indexes to draw: all of them for a short list; otherwise those in view plus a margin,
 *  and `keep` (the row holding focus) even when it is scrolled away, so focus never drops. */
export function rowsToDraw(count: number, rowHeight: number, top: number, height: number, keep = -1): number[] {
  let from = 0
  let to = count
  if (count > VIRTUAL_FROM) {
    from = Math.max(0, Math.floor(top / rowHeight) - OVERSCAN)
    to = Math.min(count, Math.ceil((top + height) / rowHeight) + OVERSCAN)
  }
  const rows = Array.from({ length: to - from }, (_, i) => from + i)
  if (keep >= to || (keep >= 0 && keep < from)) rows.push(keep)
  return rows
}

/** The rows of the scrolling element `ref` to draw, redrawn on scroll and resize. */
export function useRows(ref: RefObject<HTMLElement | null>, count: number, rowHeight: number, keep?: number): number[] {
  const [view, setView] = useState({ top: 0, height: 0 })
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setView({ top: el.scrollTop, height: el.clientHeight })
    update()
    el.addEventListener('scroll', update, { passive: true })
    const resize = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(update)
    resize?.observe(el)
    return () => {
      el.removeEventListener('scroll', update)
      resize?.disconnect()
    }
  }, [ref])
  return rowsToDraw(count, rowHeight, view.top, view.height, keep)
}

/** Scrolls `el` just enough to show row `index` (keyboard moves). */
export function scrollToRow(el: HTMLElement, index: number, rowHeight: number): void {
  const top = index * rowHeight
  if (top < el.scrollTop) el.scrollTop = top
  else if (top + rowHeight > el.scrollTop + el.clientHeight) el.scrollTop = top + rowHeight - el.clientHeight
}
