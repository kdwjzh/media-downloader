import { CheckCircle, Warning, X } from '@phosphor-icons/react'
import type { CSSProperties } from 'react'
import { type TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { formatBytes, formatDuration } from '../format'
import { addAgain, cancel, openFolder, openLog, remove, retry } from '../stores/queue'
import { type QueueItem, RETRYABLE } from '../types'
import { Button } from './Button'
import { useRowTitle } from './rowTitle'
import { FormatTag, Thumb } from './Thumb'

function ProgressBar({ percent, label }: { percent?: number; label: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      className="h-1.5 overflow-hidden rounded-full bg-divider"
    >
      {percent === undefined ? (
        // No number exists for this phase, so the bar sweeps instead of filling.
        <div className="h-full w-[30%] animate-sweep rounded-full bg-accent motion-reduce:w-full motion-reduce:animate-none motion-reduce:opacity-40" />
      ) : (
        <div className="h-full rounded-full bg-accent" style={{ width: `${percent}%` }} />
      )}
    </div>
  )
}

/** Turned to it, nothing has come in yet: the first seconds, a 403 retry, a skipped file. */
function isStarting(item: QueueItem): boolean {
  return item.status === 'downloading' && !item.doneBytes && item.totalBytes === undefined
}

/** The bar's value: only a download with a real percentage fills it. */
function barPercent(item: QueueItem): number | undefined {
  if (isStarting(item)) return undefined
  return item.status === 'downloading' || item.status === 'retrying' ? item.percent : undefined
}

function statusLabel(item: QueueItem, t: TFunction): string {
  if (isStarting(item)) return t('status.starting')
  if (item.status === 'downloading' && item.percent === undefined) return t('status.downloadingNoPercent')
  return t(`status.${item.status}`, { percent: item.percent, n: item.attempt })
}

function failedText(item: QueueItem, t: TFunction): string {
  const code = item.error ?? 'unknown'
  return `${t('status.failed', { title: t(`error.${code}.title`) })} ${t(`error.${code}.hint`)}`
}

/** What happened (brick red) and the next step; also the full text over a cut-off row. */
function FailedMessage({ item }: { item: QueueItem }) {
  const { t } = useTranslation()
  const code = item.error ?? 'unknown'
  return (
    <>
      <span className="font-medium text-danger">{t('status.failed', { title: t(`error.${code}.title`) })}</span>{' '}
      <span className="text-text">{t(`error.${code}.hint`)}</span>
    </>
  )
}

function Status({ item }: { item: QueueItem }) {
  const { t } = useTranslation()
  switch (item.status) {
    case 'downloading':
      return (
        <>
          <span>{statusLabel(item, t)}</span>
          {!isStarting(item) && item.doneBytes !== undefined && (
            <span>
              {formatBytes(item.doneBytes)}
              {item.totalBytes !== undefined && ` / ${formatBytes(item.totalBytes)}`}
            </span>
          )}
          {item.speedBps !== undefined && <span>{t('status.speed', { speed: formatBytes(item.speedBps) })}</span>}
          {item.etaSec !== undefined && <span>{t('status.eta', { time: formatDuration(item.etaSec) })}</span>}
        </>
      )
    case 'done':
      return (
        <span className="flex items-center gap-1 text-success">
          <CheckCircle size={16} aria-hidden="true" />
          {item.skipped ? t('status.skipped') : t('status.done')}
          {item.sizeBytes !== undefined && <span className="ml-2">{formatBytes(item.sizeBytes)}</span>}
        </span>
      )
    case 'failed': {
      const code = item.error ?? 'unknown'
      return (
        <>
          <span data-detail className="line-clamp-2 whitespace-normal" title={failedText(item, t)}>
            {/* Inside the text so it sits on the first line whether the message takes one line or two. */}
            <Warning size={16} aria-hidden="true" className="mr-1 inline align-text-bottom text-danger" />
            <FailedMessage item={item} />
          </span>
          {code === 'unknown' && (
            <button
              type="button"
              onClick={() => void openLog()}
              className="flex h-6 shrink-0 cursor-pointer items-center text-accent underline"
            >
              {t('action.openLog')}
            </button>
          )}
        </>
      )
    }
    default:
      return <span>{statusLabel(item, t)}</span>
  }
}

function Actions({ item, title, onRemoved }: { item: QueueItem; title: string; onRemoved: () => void }) {
  const { t } = useTranslation()
  // Several rows carry the same button; the title tells a screen reader which row.
  const named = (key: string) => ({ 'aria-label': `${t(key)}: ${title}` })
  // The first button keeps one key in every status, so React keeps the same element
  // and focus stays in the row when the buttons change with the status.
  const removeButton = (key: string) => (
    <Button
      key={key}
      variant="icon"
      {...named('action.remove')}
      title={t('action.remove')}
      onClick={() => void remove(item.id).then(onRemoved)}
    >
      <X size={16} aria-hidden="true" />
    </Button>
  )
  switch (item.status) {
    case 'done':
      return [
        <Button key="first" {...named('action.openFolder')} onClick={() => void openFolder(item.id)}>
          {t('action.openFolder')}
        </Button>,
        removeButton('second'),
      ]
    case 'failed':
      return RETRYABLE.has(item.error ?? 'unknown')
        ? [
            <Button key="first" {...named('action.retry')} onClick={() => void retry(item.id)}>
              {t('action.retry')}
            </Button>,
            removeButton('second'),
          ]
        : [removeButton('first')]
    case 'cancelled':
      return [
        <Button key="first" {...named('action.addAgain')} onClick={() => void addAgain(item.id)}>
          {t('action.addAgain')}
        </Button>,
        removeButton('second'),
      ]
    default:
      return [
        <Button key="first" variant="text" {...named('action.cancel')} onClick={() => void cancel(item.id)}>
          {t('action.cancel')}
        </Button>,
      ]
  }
}

const HAS_BAR: ReadonlySet<QueueItem['status']> = new Set([
  'fetching',
  'downloading',
  'retrying',
  'converting',
  'merging',
])

interface Props {
  item: QueueItem
  /** The row's own remove button took it away: focus has to go somewhere else. */
  onRemoved?: () => void
  /** Its place in a virtual list. */
  style?: CSSProperties
}

export function QueueRow({ item, onRemoved = () => {}, style }: Props) {
  const { t } = useTranslation()
  const title = item.title ?? item.url
  const { rowProps, titleLine } = useRowTitle(title, item.status === 'failed' && <FailedMessage item={item} />)
  return (
    // Fixed height in every state so the list never jumps when a status changes.
    <li data-id={item.id} style={style} className="relative flex h-18 items-center gap-3 px-3" {...rowProps}>
      <Thumb format={item.format} src={item.thumb} loading={item.status === 'fetching'} />
      <div className="relative flex min-w-0 flex-1 flex-col gap-1">
        {titleLine}
        {item.status === 'failed' ? (
          // A failed row has no bar, so the message may use that space for a second
          // line: the hint is the next step and must not be cut off in a narrow window.
          <div className="flex h-8 items-center gap-1 text-xs">
            <Status item={item} />
          </div>
        ) : (
          <>
            <div className="flex h-4 items-center gap-3 overflow-hidden text-xs whitespace-nowrap text-text-muted tabular-nums">
              <Status item={item} />
            </div>
            <div className="h-1.5">
              {HAS_BAR.has(item.status) && <ProgressBar percent={barPercent(item)} label={statusLabel(item, t)} />}
            </div>
          </>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end justify-between self-stretch py-2">
        <FormatTag format={item.format} />
        {/* Focus stays on the first button as it turns into the next action (Cancel → Add
            again): a held Enter would flip it back and forth, so only the first press counts. */}
        <div className="flex items-center gap-1" onKeyDown={(e) => e.repeat && e.preventDefault()}>
          <Actions item={item} title={title} onRemoved={onRemoved} />
        </div>
      </div>
    </li>
  )
}
