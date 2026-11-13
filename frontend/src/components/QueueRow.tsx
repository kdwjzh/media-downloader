import { CheckCircle, Warning, X } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { formatBytes, formatDuration } from '../format'
import { type QueueItem, RETRYABLE } from '../types'
import { Button } from './Button'
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

function Status({ item }: { item: QueueItem }) {
  const { t } = useTranslation()
  switch (item.status) {
    case 'downloading':
      return (
        <>
          <span>{t('status.downloading', { percent: item.percent })}</span>
          {item.doneBytes !== undefined && (
            <span>
              {formatBytes(item.doneBytes)}
              {item.totalBytes !== undefined && ` / ${formatBytes(item.totalBytes)}`}
            </span>
          )}
          {item.speedBps !== undefined && <span>{t('status.speed', { speed: formatBytes(item.speedBps) })}</span>}
          {item.etaSec !== undefined && <span>{t('status.eta', { time: formatDuration(item.etaSec) })}</span>}
        </>
      )
    case 'retrying':
      return <span>{t('status.retrying', { n: item.attempt })}</span>
    case 'done':
      return (
        <span className="flex items-center gap-1 text-success">
          <CheckCircle size={16} aria-hidden="true" />
          {t('status.done')}
          {item.sizeBytes !== undefined && <span className="ml-2">{formatBytes(item.sizeBytes)}</span>}
        </span>
      )
    case 'failed': {
      const code = item.error ?? 'unknown'
      const title = t('status.failed', { title: t(`error.${code}.title`) })
      const hint = t(`error.${code}.hint`)
      return (
        <>
          <Warning size={16} aria-hidden="true" className="shrink-0 self-start text-danger" />
          <span className="line-clamp-2 whitespace-normal" title={`${title} ${hint}`}>
            <span className="font-medium text-danger">{title}</span> <span className="text-text">{hint}</span>
          </span>
          {code === 'unknown' && (
            <button type="button" className="flex h-6 shrink-0 cursor-pointer items-center text-accent underline">
              {t('action.openLog')}
            </button>
          )}
        </>
      )
    }
    default:
      return <span>{t(`status.${item.status}`)}</span>
  }
}

function Actions({ item, title }: { item: QueueItem; title: string }) {
  const { t } = useTranslation()
  // Several rows carry the same button; the title tells a screen reader which row.
  const named = (key: string) => ({ 'aria-label': `${t(key)}: ${title}` })
  const remove = (
    <Button variant="icon" {...named('action.remove')} title={t('action.remove')}>
      <X size={16} aria-hidden="true" />
    </Button>
  )
  switch (item.status) {
    case 'done':
      return (
        <>
          <Button {...named('action.openFolder')}>{t('action.openFolder')}</Button>
          {remove}
        </>
      )
    case 'failed':
      return (
        <>
          {RETRYABLE.has(item.error ?? 'unknown') && <Button {...named('action.retry')}>{t('action.retry')}</Button>}
          {remove}
        </>
      )
    case 'cancelled':
      return (
        <>
          <Button {...named('action.addAgain')}>{t('action.addAgain')}</Button>
          {remove}
        </>
      )
    default:
      return (
        <Button variant="text" {...named('action.cancel')}>
          {t('action.cancel')}
        </Button>
      )
  }
}

const HAS_BAR: ReadonlySet<QueueItem['status']> = new Set([
  'fetching',
  'downloading',
  'retrying',
  'converting',
  'merging',
])

export function QueueRow({ item }: { item: QueueItem }) {
  const { t } = useTranslation()
  const title = item.title ?? item.url
  // Only downloading and retrying carry a real percentage.
  const percent = item.status === 'downloading' || item.status === 'retrying' ? item.percent : undefined
  return (
    // Fixed height in every state so the list never jumps when a status changes.
    <li className="flex h-18 items-center gap-3 px-3">
      <Thumb format={item.format} color={item.thumb} loading={item.status === 'fetching'} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="truncate font-medium" title={title}>
          {title}
        </p>
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
              {HAS_BAR.has(item.status) && (
                <ProgressBar percent={percent} label={t(`status.${item.status}`, { percent, n: item.attempt })} />
              )}
            </div>
          </>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end justify-between self-stretch py-2">
        <FormatTag format={item.format} />
        <div className="flex items-center gap-1">
          <Actions item={item} title={title} />
        </div>
      </div>
    </li>
  )
}
