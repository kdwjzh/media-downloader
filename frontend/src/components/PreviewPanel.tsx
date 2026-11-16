import { ListBullets, Warning, X } from '@phosphor-icons/react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { formatBytes, formatDuration } from '../format'
import { openLog } from '../stores/queue'
import { addPreview, choose, closePreview, heightsOf, lookUp, resolve, usePreview } from '../stores/preview'
import { type Format, MP3_BITRATES, type MediaInfo, RETRYABLE } from '../types'
import { Button } from './Button'
import { Thumb } from './Thumb'

const FORMATS: Format[] = ['mp3', 'mp4']

interface Props {
  /** The preview went away by the person's hand (added or closed): focus goes back to the URL box. */
  onDone: () => void
}

function Ready({ info, onDone }: Props & { info: MediaInfo }) {
  const { t } = useTranslation()
  const id = useId()
  const choice = usePreview((s) => s.choice)
  const heights = heightsOf(info)
  const { format, quality } = resolve(info, choice)
  const isAudio = format === 'mp3'
  const size = info.options.find((o) => o.format === format && o.quality === quality)?.sizeBytes

  return (
    <>
      <Thumb format={format} src={info.thumb} size="preview" />
      <div className="flex min-w-0 flex-1 flex-col">
        <h2 className="line-clamp-2 pr-8 text-base font-medium" title={info.title}>
          {info.title}
        </h2>
        <p className="flex gap-3 text-xs text-text-muted tabular-nums">
          {info.channel && <span className="truncate">{info.channel}</span>}
          <span>{formatDuration(info.durationSec)}</span>
        </p>
        <div className="mt-auto flex items-end gap-3">
          <div className="flex flex-col gap-1">
            <span id={`${id}-format`} className="text-xs text-text-muted">
              {t('format.label')}
            </span>
            <div
              role="radiogroup"
              aria-labelledby={`${id}-format`}
              className="flex h-9 items-center rounded-lg border border-border bg-surface p-0.5"
            >
              {FORMATS.map((f) => (
                <label key={f} className="cursor-pointer has-disabled:cursor-not-allowed has-disabled:opacity-45">
                  <input
                    type="radio"
                    name={`${id}-format`}
                    className="peer sr-only"
                    checked={format === f}
                    // No picture, no MP4 (contract 2.3).
                    disabled={f === 'mp4' && heights.length === 0}
                    onChange={() => choose({ format: f })}
                  />
                  <span className="flex h-7.5 min-w-12 items-center justify-center rounded-md px-3 transition-colors duration-150 peer-checked:bg-accent peer-checked:text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent peer-not-checked:peer-enabled:hover:bg-accent-soft">
                    {t(`format.${f}`)}
                  </span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-quality`} className="text-xs text-text-muted">
              {t(isAudio ? 'quality.audioLabel' : 'quality.videoLabel')}
            </label>
            <select
              id={`${id}-quality`}
              className="h-9 cursor-pointer rounded-lg border border-border bg-surface px-2"
              value={quality}
              onChange={(e) => choose(isAudio ? { mp3Bitrate: Number(e.target.value) } : { mp4Height: Number(e.target.value) })}
            >
              {(isAudio ? MP3_BITRATES : heights).map((n) => (
                <option key={n} value={n}>
                  {t(isAudio ? 'quality.kbps' : 'quality.exact', { n })}
                </option>
              ))}
            </select>
          </div>
          <Button variant="primary" className="ml-auto" autoFocus onClick={() => void addPreview().then((added) => added && onDone())}>
            {t('action.addToQueue')}
          </Button>
        </div>
        {/* Fixed-height line: the 4K note appears here without resizing the panel. */}
        <p className="mt-1 flex h-4 gap-3 overflow-hidden text-xs whitespace-nowrap text-text-muted tabular-nums">
          <span>{size === undefined ? t('size.unknown') : t('size.approx', { size: formatBytes(size) })}</span>
          {!isAudio && quality === 2160 && (
            <span className="truncate" title={t('preview.note4k')}>
              {t('preview.note4k')}
            </span>
          )}
        </p>
      </div>
    </>
  )
}

export function PreviewPanel({ onDone }: Props) {
  const { t } = useTranslation()
  const preview = usePreview((s) => s.preview)
  const format = usePreview((s) => s.choice.format)
  if (!preview) return null
  const isError = preview.kind === 'error'
  return (
    // Same height in every state, so the queue below moves only once.
    <section
      aria-label={t('preview.title')}
      aria-busy={preview.kind === 'loading'}
      className={`relative flex h-43 shrink-0 gap-4 rounded-[10px] p-4 ${isError ? 'bg-danger-soft' : 'bg-surface'}`}
    >
      {preview.kind === 'loading' && (
        <>
          <Thumb format={format} size="preview" loading />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <div className="h-5 w-3/5 animate-skeleton rounded bg-divider motion-reduce:animate-none" />
            <div className="h-4 w-1/4 animate-skeleton rounded bg-divider motion-reduce:animate-none" />
            <p role="status" className="mt-auto">
              {t('preview.loading')}
            </p>
            <p className="line-clamp-2 text-xs wrap-anywhere text-text-muted">{preview.url}</p>
          </div>
        </>
      )}
      {preview.kind === 'ready' && <Ready info={preview.info} onDone={onDone} />}
      {preview.kind === 'playlist' && (
        <div className="flex min-w-0 flex-1 gap-3">
          <ListBullets size={20} aria-hidden="true" className="shrink-0 text-text-muted" />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <h2 className="line-clamp-2 pr-8 text-base font-medium" title={preview.playlist.title}>
              {preview.playlist.title}
            </h2>
            <p className="text-xs text-text-muted tabular-nums">
              {t('preview.playlistCount', { count: preview.playlist.entries.length })}
            </p>
            <p className="mt-auto">{t('preview.playlistPending')}</p>
          </div>
        </div>
      )}
      {preview.kind === 'error' && (
        <div role="alert" className="flex min-w-0 flex-1 gap-3">
          <Warning size={20} aria-hidden="true" className="shrink-0 text-danger" />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <h2 className="pr-8 font-medium text-danger">{t(`error.${preview.code}.title`)}</h2>
            <p>{t(`error.${preview.code}.hint`)}</p>
            <p className="line-clamp-2 text-xs wrap-anywhere text-text-muted">{preview.url}</p>
            <div className="mt-auto flex justify-end gap-2">
              {preview.code === 'unknown' && <Button onClick={() => void openLog()}>{t('action.openLog')}</Button>}
              {RETRYABLE.has(preview.code) && (
                <Button onClick={() => void lookUp(preview.url)}>{t('action.retry')}</Button>
              )}
            </div>
          </div>
        </div>
      )}
      <Button
        variant="icon"
        className="absolute top-2 right-2"
        aria-label={t('preview.close')}
        title={t('preview.close')}
        onClick={() => {
          closePreview()
          onDone()
        }}
      >
        <X size={16} aria-hidden="true" />
      </Button>
    </section>
  )
}
