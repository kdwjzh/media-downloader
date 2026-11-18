import { type FocusEvent, type ReactNode, useState } from 'react'

/** A list row's title line. Keyboard users never see the title attribute: while focus is in
 *  a row whose title is cut off, the full title lies over the text column instead (design
 *  step 5). A failed queue row's error can be cut off the same way (`[data-detail]`, two
 *  lines): only then does the overlay add `detail` under the title. Spread `rowProps` on the <li>. */
export function useRowTitle(title: string, detail?: ReactNode) {
  // What is cut off right now: the overlay repeats only that.
  const [cut, setCut] = useState({ title: false, detail: false })
  const rowProps = {
    onFocus: (e: FocusEvent<HTMLElement>) => {
      const p = e.currentTarget.querySelector('[data-title]')
      const d = e.currentTarget.querySelector('[data-detail]')
      // A control inside the text column (the log link) would end up under the overlay.
      if (p?.parentElement?.contains(e.target)) return setCut({ title: false, detail: false })
      setCut({ title: !!p && p.scrollWidth > p.clientWidth, detail: !!d && d.scrollHeight > d.clientHeight })
    },
    onBlur: (e: FocusEvent<HTMLElement>) => {
      if (!e.currentTarget.contains(e.relatedTarget)) setCut({ title: false, detail: false })
    },
  }
  const titleLine = (
    <>
      <p data-title className="truncate font-medium" title={title}>
        {title}
      </p>
      {(cut.title || cut.detail) && (
        <div
          aria-hidden="true"
          className="absolute -inset-x-1 top-0 z-20 rounded-lg border border-border bg-surface px-1 wrap-anywhere"
        >
          <p className="line-clamp-3 font-medium">{title}</p>
          {cut.detail && detail && <p className="text-xs">{detail}</p>}
        </div>
      )}
    </>
  )
  return { rowProps, titleLine }
}
