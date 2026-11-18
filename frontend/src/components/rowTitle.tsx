import { type FocusEvent, type ReactNode, useState } from 'react'

/** A list row's title line. Keyboard users never see the title attribute: while focus is in
 *  a row whose title is cut off, the full title lies over the text column instead (design
 *  step 5). A failed queue row's error can be cut off the same way (`[data-detail]`, two
 *  lines): then the overlay carries `detail` under the title. Spread `rowProps` on the <li>. */
export function useRowTitle(title: string, detail?: ReactNode) {
  const [full, setFull] = useState(false)
  const rowProps = {
    onFocus: (e: FocusEvent<HTMLElement>) => {
      const p = e.currentTarget.querySelector('[data-title]')
      const d = e.currentTarget.querySelector('[data-detail]')
      // A control inside the text column (the log link) would end up under the overlay.
      if (p?.parentElement?.contains(e.target)) return setFull(false)
      setFull((!!p && p.scrollWidth > p.clientWidth) || (!!d && d.scrollHeight > d.clientHeight))
    },
    onBlur: (e: FocusEvent<HTMLElement>) => {
      if (!e.currentTarget.contains(e.relatedTarget)) setFull(false)
    },
  }
  const titleLine = (
    <>
      <p data-title className="truncate font-medium" title={title}>
        {title}
      </p>
      {full && (
        <div
          aria-hidden="true"
          className="absolute -inset-x-1 top-0 z-20 rounded-lg border border-border bg-surface px-1 wrap-anywhere"
        >
          <p className="line-clamp-3 font-medium">{title}</p>
          {detail && <p className="text-xs">{detail}</p>}
        </div>
      )}
    </>
  )
  return { rowProps, titleLine }
}
