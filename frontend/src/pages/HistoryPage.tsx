import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/Button'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { HistoryRow } from '../components/HistoryRow'
import { Sleeves } from '../components/Sleeves'
import { clearHistory, deleteEntry, loadHistory, useHistory } from '../stores/history'
import { goToUrlBox, usePage } from '../stores/page'
import type { HistoryEntry } from '../types'
import { useRows } from '../virtual'

const ROW = 72 // MASTER: list rows, the same as the queue

function HistoryList({ entries, onEmptied }: { entries: HistoryEntry[]; onEmptied: () => void }) {
  const list = useRef<HTMLUListElement>(null)
  const added = useHistory((s) => s.added)
  // The row holding focus stays drawn while scrolled away, or focus would drop to the page.
  const [focused, setFocused] = useState<string>()
  const keep = focused === undefined ? -1 : entries.findIndex((entry) => entry.id === focused)
  const rows = useRows(list, entries.length, ROW, keep)
  // After a delete, focus goes to the delete button of the row now in that place (decisions/0015).
  const focusNext = useRef<string>(undefined)
  useEffect(() => {
    const id = focusNext.current
    focusNext.current = undefined
    if (id !== undefined) list.current?.querySelector<HTMLElement>(`[data-id="${id}"] [data-delete]`)?.focus()
  }, [entries])

  async function remove(entry: HistoryEntry, index: number) {
    // Set before the call: the list may redraw before the call returns.
    focusNext.current = (entries[index + 1] ?? entries[index - 1])?.id
    if (!(await deleteEntry(entry))) focusNext.current = undefined
    else if (focusNext.current === undefined) onEmptied()
  }

  return (
    <ul
      ref={list}
      aria-labelledby="history-title"
      onFocus={(e) => setFocused((e.target as HTMLElement).closest('li')?.dataset.id)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setFocused(undefined)
      }}
      className="relative min-h-0 flex-1 overflow-y-auto rounded-[10px] bg-surface"
    >
      {/* Holds the full height so the scroll bar is true; rows are placed by index. */}
      <li aria-hidden="true" style={{ height: entries.length * ROW }} />
      {rows.map((i) => (
        <HistoryRow
          key={entries[i].id}
          entry={entries[i]}
          added={added.has(entries[i].id)}
          onDelete={() => void remove(entries[i], i)}
          style={{
            position: 'absolute',
            insetInline: 0,
            top: i * ROW,
            borderTop: i > 0 ? '1px solid var(--color-divider)' : undefined,
          }}
        />
      ))}
    </ul>
  )
}

export function HistoryPage() {
  const { t } = useTranslation()
  const bodyId = useId()
  const showing = usePage((s) => s.page === 'history')
  const { entries, status } = useHistory()
  const [askClear, setAskClear] = useState(false)
  const goButton = useRef<HTMLButtonElement>(null)
  const [focusGo, setFocusGo] = useState(0)

  // Loaded the first time the screen shows; historyAdded keeps it current after that.
  useEffect(() => {
    if (showing) void loadHistory()
  }, [showing])

  // The list is gone (last entry deleted, or cleared): focus to the empty screen's button.
  useEffect(() => {
    if (focusGo > 0) goButton.current?.focus()
  }, [focusGo])
  const emptied = () => setFocusGo((n) => n + 1)

  return (
    <main className="flex min-w-0 flex-1 flex-col gap-4 p-6 pl-2">
      <div className="flex h-8 items-center gap-2">
        <h1 id="history-title" className="mr-auto font-display text-xl font-semibold">
          {t('history.title')}
        </h1>
        {status === 'loaded' && entries.length > 0 && (
          <Button variant="dangerOutline" onClick={() => setAskClear(true)}>
            {t('history.clear')}
          </Button>
        )}
      </div>
      {status === 'failed' && (
        <div role="alert" className="flex items-center gap-3">
          <p className="text-danger">{t('history.loadFailed')}</p>
          <Button onClick={() => void loadHistory()}>{t('action.retry')}</Button>
        </div>
      )}
      {status === 'loaded' &&
        (entries.length > 0 ? (
          <HistoryList entries={entries} onEmptied={emptied} />
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
            <Sleeves />
            <h2 className="text-base font-medium">{t('history.emptyTitle')}</h2>
            <p id={bodyId} className="mb-2 max-w-md text-text-muted">
              {t('history.emptyBody')}
            </p>
            <Button ref={goButton} aria-describedby={bodyId} onClick={goToUrlBox}>
              {t('history.goToDownloads')}
            </Button>
          </div>
        ))}
      <ConfirmDialog
        open={askClear}
        title={t('history.confirmTitle', { count: entries.length })}
        body={t('history.confirmBody')}
        keepLabel={t('action.cancel')}
        confirmLabel={t('history.clear')}
        onKeep={() => setAskClear(false)}
        onConfirm={() => {
          setAskClear(false)
          void clearHistory().then(emptied)
        }}
      />
    </main>
  )
}
