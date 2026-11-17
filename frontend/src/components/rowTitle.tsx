import { type FocusEvent, useState } from 'react'

/** A list row's title line. Keyboard users never see the title attribute: while focus is in
 *  a row whose title is cut off, the full title lies over the text column instead (design
 *  step 5). Spread `rowProps` on the row's <li>. */
export function useRowTitle(title: string) {
  const [full, setFull] = useState(false)
  const rowProps = {
    onFocus: (e: FocusEvent<HTMLElement>) => {
      const p = e.currentTarget.querySelector('[data-title]')
      setFull(!!p && p.scrollWidth > p.clientWidth)
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
        <p
          aria-hidden="true"
          className="absolute -inset-x-1 top-0 z-20 line-clamp-3 rounded-lg border border-border bg-surface px-1 font-medium wrap-anywhere"
        >
          {title}
        </p>
      )}
    </>
  )
  return { rowProps, titleLine }
}
