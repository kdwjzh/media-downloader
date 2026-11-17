import { useRef, useState } from 'react'
import type { QueueItem } from '../types'
import { useRows } from '../virtual'
import { QueueRow } from './QueueRow'

const QUEUE_ROW = 72 // MASTER: list rows

interface Props {
  items: QueueItem[]
  onRemoved: () => void
}

/** The queue's rows; past 100 only those near the view exist (MASTER: lists). */
export function QueueList({ items, onRemoved }: Props) {
  const list = useRef<HTMLUListElement>(null)
  // The row holding focus stays drawn while scrolled away, or focus would drop to the page.
  const [focused, setFocused] = useState<string>()
  const keep = focused === undefined ? -1 : items.findIndex((item) => item.id === focused)
  const rows = useRows(list, items.length, QUEUE_ROW, keep)
  return (
    <ul
      ref={list}
      onFocus={(e) => setFocused((e.target as HTMLElement).closest('li')?.dataset.id)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setFocused(undefined)
      }}
      className="relative min-h-0 overflow-y-auto rounded-[10px] bg-surface"
    >
      {/* Holds the full height so the scroll bar is true; rows are placed by index. */}
      <li aria-hidden="true" style={{ height: items.length * QUEUE_ROW }} />
      {rows.map((i) => (
        <QueueRow
          key={items[i].id}
          item={items[i]}
          onRemoved={onRemoved}
          style={{
            position: 'absolute',
            insetInline: 0,
            top: i * QUEUE_ROW,
            // Lines between rows; the first row has none (MASTER: lists).
            borderTop: i > 0 ? '1px solid var(--color-divider)' : undefined,
          }}
        />
      ))}
    </ul>
  )
}
