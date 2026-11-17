import { CheckCircle, Trash } from '@phosphor-icons/react'
import type { CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { formatBytes, formatTime } from '../format'
import { downloadAgain, openFolder } from '../stores/history'
import type { HistoryEntry } from '../types'
import { Button } from './Button'
import { useRowTitle } from './rowTitle'
import { FormatTag, Thumb } from './Thumb'

interface Props {
  entry: HistoryEntry
  added: boolean
  onDelete: () => void
  style?: CSSProperties
}

/** The queue's row with the size and time in the status line and three buttons
 *  (pages/history.md). */
export function HistoryRow({ entry, added, onDelete, style }: Props) {
  const { t, i18n } = useTranslation()
  const { rowProps, titleLine } = useRowTitle(entry.title)
  // Several rows carry the same button; the title tells a screen reader which row.
  const named = (key: string) => ({ 'aria-label': `${t(key)}: ${entry.title}` })
  return (
    <li data-id={entry.id} style={style} className="relative flex h-18 items-center gap-3 px-3" {...rowProps}>
      <Thumb format={entry.format} src={entry.thumb} />
      <div className="relative flex min-w-0 flex-1 flex-col gap-1">
        {titleLine}
        {/* Two lines: the row has no bar, and in the narrowest English window the time alone
            fills the column. Time first, so the size and the mark wrap together. */}
        <div className="flex h-8 flex-wrap content-start gap-x-3 overflow-hidden text-xs leading-4 whitespace-nowrap text-text-muted tabular-nums">
          <span>{formatTime(entry.finishedAt, i18n.language)}</span>
          <span>{formatBytes(entry.sizeBytes)}</span>
          {added && (
            <span className="flex items-center gap-1 text-success">
              <CheckCircle size={16} aria-hidden="true" />
              {t('history.addedToQueue')}
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end justify-between self-stretch py-2">
        <FormatTag format={entry.format} />
        <div className="flex items-center gap-1">
          <Button {...named('history.downloadAgain')} onClick={() => void downloadAgain(entry)}>
            {t('history.downloadAgain')}
          </Button>
          <Button {...named('action.openFolder')} onClick={() => void openFolder(entry.id)}>
            {t('action.openFolder')}
          </Button>
          <Button
            variant="icon"
            data-delete
            {...named('history.deleteEntry')}
            title={t('history.deleteEntry')}
            // Focus moves to the next row's delete button, so a held Enter would delete row
            // after row: only the first press counts.
            onKeyDown={(e) => e.repeat && e.preventDefault()}
            onClick={onDelete}
          >
            <Trash size={16} aria-hidden="true" />
          </Button>
        </div>
      </div>
    </li>
  )
}
