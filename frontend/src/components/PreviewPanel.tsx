import { Warning, X } from '@phosphor-icons/react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatBytes, formatDuration } from '../format'
import { type Format, type MediaInfo, type Preview, RETRYABLE } from '../types'
import { Button } from './Button'
import { Thumb } from './Thumb'

const FORMATS: Format[] = ['mp3', 'mp4']

interface Props {
  preview: Preview
  /** Remembered from the last download. */
  defaults: { format: Format; bitrate: number; height: number }
}

function Ready({ info, defaults }: Omit<Props, 'preview'> & { info: MediaInfo }) {
  const { t } = useTranslation()
  const id = useId()
  const [format, setFormat] = useState(defaults.format)
  const [bitrate, setBitrate] = useState(defaults.bitrate)
  const qualities = (f: Format) => info.options.filter((o) => o.format === f).map((o) => o.quality)
  const heights = qualities('mp4').sort((a, b) => b - a)
  // The saved height is a ceiling: fall back to the best this video has under it.
  const [height, setHeight] = useState(heights.find((h) => h <= defaults.height) ?? heights.at(-1) ?? 0)

  const isAudio = format === 'mp3'
  const quality = isAudio ? bitrate : height
  const size = info.options.find((o) => o.format === format && o.quality === quality)?.sizeBytes

  return (
    <>
      <Thumb format={format} color={info.thumb} size="preview" />
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
                <label key={f} className="cursor-pointer">
                  <input
                    type="radio"
                    name={`${id}-format`}
                    className="peer sr-only"
                    checked={format === f}
                    onChange={() => setFormat(f)}
                  />
                  <span className="flex h-7.5 min-w-12 items-center justify-center rounded-md px-3 transition-colors duration-150 peer-checked:bg-accent peer-checked:text-on-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent peer-not-checked:hover:bg-accent-soft">
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
              onChange={(e) => (isAudio ? setBitrate : setHeight)(Number(e.target.value))}
            >
              {isAudio
                ? qualities('mp3').map((n) => (
                    <option key={n} value={n}>
                      {t('quality.kbps', { n })}
                    </option>
                  ))
                : heights.map((n) => (
                    <option key={n} value={n}>
                      {t('quality.exact', { n })}
                    </option>
                  ))}
            </select>
          </div>
          <Button variant="primary" className="ml-auto" autoFocus>
            {t('action.addToQueue')}
          </Button>
        </div>
        {/* Fixed-height line: the 4K note appears here without resizing the panel. */}
        <p className="mt-1 flex h-4 gap-3 overflow-hidden text-xs whitespace-nowrap text-text-muted tabular-nums">
          <span>{size === undefined ? t('size.unknown') : t('size.approx', { size: formatBytes(size) })}</span>
          {!isAudio && height === 2160 && <span className="truncate" title={t('preview.note4k')}>{t('preview.note4k')}</span>}
        </p>
      </div>
    </>
  )
}

export function PreviewPanel({ preview, defaults }: Props) {
  const { t } = useTranslation()
  const isError = preview.kind === 'error'
  return (
    // Same height in all three states, so the queue below moves only once.
    <section
      aria-busy={preview.kind === 'loading'}
      className={`relative flex h-43 shrink-0 gap-4 rounded-[10px] p-4 ${isError ? 'bg-danger-soft' : 'bg-surface'}`}
    >
      {preview.kind === 'loading' && (
        <>
          <Thumb format={defaults.format} size="preview" loading />
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
      {preview.kind === 'ready' && (
        // Remount per video so the remembered choices are applied afresh.
        <Ready key={preview.info.url} info={preview.info} defaults={defaults} />
      )}
      {preview.kind === 'error' && (
        <div role="alert" className="flex min-w-0 flex-1 gap-3">
          <Warning size={20} aria-hidden="true" className="shrink-0 text-danger" />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <h2 className="pr-8 font-medium text-danger">{t(`error.${preview.code}.title`)}</h2>
            <p>{t(`error.${preview.code}.hint`)}</p>
            <p className="line-clamp-2 text-xs wrap-anywhere text-text-muted">{preview.url}</p>
            <div className="mt-auto flex justify-end gap-2">
              {preview.code === 'unknown' && <Button>{t('action.openLog')}</Button>}
              {RETRYABLE.has(preview.code) && <Button>{t('action.retry')}</Button>}
            </div>
          </div>
        </div>
      )}
      <Button
        variant="icon"
        className="absolute top-2 right-2"
        aria-label={t('preview.close')}
        title={t('preview.close')}
      >
        <X size={16} aria-hidden="true" />
      </Button>
    </section>
  )
}
