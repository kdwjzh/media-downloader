import { Check, X } from '@phosphor-icons/react'
import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDuration } from '../format'
import { addPlaylist, choose, closePreview, usePreview } from '../stores/preview'
import { MP3_BITRATES, MP4_HEIGHTS, type PlaylistInfo } from '../types'
import { scrollToRow, useRows } from '../virtual'
import { Button } from './Button'
import { FormatSwitch } from './FormatSwitch'
import { Thumb } from './Thumb'

export const PLAYLIST_ROW = 56 // pages/playlist.md

interface Props {
  playlist: PlaylistInfo
  /** The screen went away by the person's hand: focus goes back to the URL box. */
  onDone: () => void
}

/** The tick list that replaces the preview and the queue for a playlist (pages/playlist.md). */
export function PlaylistPanel({ playlist, onDone }: Props) {
  const { t } = useTranslation()
  const id = useId()
  const choice = usePreview((s) => s.choice)
  const entries = playlist.entries
  // Unavailable entries cannot be ticked and are not counted (contract 2.4).
  const usable = useMemo(() => entries.flatMap((entry, i) => (entry.available ? [i] : [])), [entries])
  const [picked, setPicked] = useState(() => new Set(usable))
  const [active, setActive] = useState(0)
  const [busy, setBusy] = useState(false)
  const list = useRef<HTMLDivElement>(null)
  const all = useRef<HTMLInputElement>(null)
  const rows = useRows(list, entries.length, PLAYLIST_ROW, active)

  const count = picked.size
  const some = count > 0 && count < usable.length
  useEffect(() => {
    if (all.current) all.current.indeterminate = some // only settable from script
  }, [some])

  const isAudio = choice.format === 'mp3'

  function toggle(i: number) {
    if (!entries[i]?.available) return
    setPicked((before) => {
      const after = new Set(before)
      if (!after.delete(i)) after.add(i)
      return after
    })
  }

  // Tab reaches the list once; arrows move inside it and Space ticks (pages/playlist.md).
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === ' ') {
      e.preventDefault()
      toggle(active)
      return
    }
    const el = e.currentTarget
    const page = Math.max(1, Math.floor(el.clientHeight / PLAYLIST_ROW) - 1)
    const moves: Record<string, number> = {
      ArrowDown: active + 1,
      ArrowUp: active - 1,
      Home: 0,
      End: entries.length - 1,
      PageDown: active + page,
      PageUp: active - page,
    }
    if (!(e.key in moves) || entries.length === 0) return
    e.preventDefault()
    const next = Math.min(entries.length - 1, Math.max(0, moves[e.key]))
    setActive(next)
    scrollToRow(el, next, PLAYLIST_ROW)
  }

  async function add() {
    setBusy(true) // one click, one batch: a second click must not add hundreds again
    const urls = usable.filter((i) => picked.has(i)).map((i) => entries[i].url) // the list's order
    if (await addPlaylist(urls)) onDone()
    else setBusy(false)
  }

  function close() {
    closePreview()
    onDone()
  }

  return (
    <section aria-labelledby={`${id}-title`} className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="relative pr-9">
        <h2 id={`${id}-title`} className="line-clamp-2 font-display text-xl font-semibold" title={playlist.title}>
          {playlist.title}
        </h2>
        <p className="flex gap-3 text-xs text-text-muted tabular-nums">
          {playlist.channel && <span className="truncate">{playlist.channel}</span>}
          <span className="shrink-0">{t('playlist.count', { count: entries.length })}</span>
        </p>
        <Button
          variant="icon"
          className="absolute top-0 right-0"
          aria-label={t('playlist.close')}
          title={t('playlist.close')}
          onClick={close}
        >
          <X size={16} aria-hidden="true" />
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <label className="flex cursor-pointer items-center gap-2 whitespace-nowrap has-disabled:cursor-not-allowed has-disabled:opacity-45">
          <input
            ref={all}
            type="checkbox"
            className="size-4 cursor-pointer accent-accent disabled:cursor-not-allowed"
            checked={usable.length > 0 && count === usable.length}
            disabled={usable.length === 0}
            // Some ticked: one press ticks them all (pages/playlist.md).
            onChange={() => setPicked(count === usable.length ? new Set() : new Set(usable))}
          />
          {t('playlist.selectAll')}
        </label>
        <span className="whitespace-nowrap text-text-muted tabular-nums">
          {t('playlist.selected', { selected: count, total: usable.length })}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2">
          <FormatSwitch inline value={choice.format} onChange={(f) => choose({ format: f })} />
          <div className="flex items-center gap-2">
            <label htmlFor={`${id}-quality`} className="text-xs whitespace-nowrap text-text-muted">
              {t(isAudio ? 'quality.audioLabel' : 'quality.videoLabel')}
            </label>
            <select
              id={`${id}-quality`}
              className="h-9 cursor-pointer rounded-lg border border-border bg-surface px-2"
              value={isAudio ? choice.mp3Bitrate : choice.mp4Height}
              onChange={(e) => choose(isAudio ? { mp3Bitrate: Number(e.target.value) } : { mp4Height: Number(e.target.value) })}
            >
              {/* Every height: what each video has is not known without looking each one up. */}
              {(isAudio ? MP3_BITRATES : MP4_HEIGHTS).map((n) => (
                <option key={n} value={n}>
                  {t(isAudio ? 'quality.kbps' : 'quality.upTo', { n })}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="rounded-[10px] bg-surface p-6 text-center text-text-muted">{t('playlist.empty')}</p>
      ) : (
        <div
          ref={list}
          role="listbox"
          aria-multiselectable="true"
          aria-labelledby={`${id}-title`}
          aria-activedescendant={`${id}-${active}`}
          tabIndex={0}
          onKeyDown={onKeyDown}
          className="group min-h-0 flex-1 overflow-y-auto rounded-[10px] bg-surface focus-visible:outline-none"
        >
          {/* Rows are placed by index, so only those near the view need to exist. */}
          <div className="relative" style={{ height: entries.length * PLAYLIST_ROW }}>
            {rows.map((i) => {
              const entry = entries[i]
              const on = picked.has(i)
              const name = entry.title ?? entry.url
              return (
                <div
                  key={i}
                  id={`${id}-${i}`}
                  role="option"
                  aria-selected={on}
                  aria-disabled={!entry.available || undefined}
                  aria-posinset={i + 1}
                  aria-setsize={entries.length}
                  style={{ top: i * PLAYLIST_ROW }}
                  onClick={() => {
                    setActive(i)
                    toggle(i)
                  }}
                  className={`absolute inset-x-0 flex h-14 items-center gap-3 px-3 ${i > 0 ? 'border-t border-divider' : ''} ${
                    entry.available ? 'cursor-pointer hover:bg-accent-soft' : ''
                  } ${i === active ? 'rounded-md group-focus-visible:outline-2 group-focus-visible:-outline-offset-2 group-focus-visible:outline-accent' : ''}`}
                >
                  <span
                    aria-hidden="true"
                    className={`grid size-4 shrink-0 place-items-center rounded border-[1.5px] ${
                      on ? 'border-accent bg-accent text-on-accent' : 'border-border bg-surface'
                    } ${entry.available ? '' : 'opacity-45'}`}
                  >
                    {on && <Check size={12} />}
                  </span>
                  <Thumb format={choice.format} src={entry.thumb} size="small" />
                  <span className="min-w-0 flex-1">
                    <span className={`block truncate ${entry.available ? 'font-medium' : 'text-text-muted'}`} title={name}>
                      {name}
                    </span>
                    {entry.channel && <span className="block truncate text-xs text-text-muted">{entry.channel}</span>}
                  </span>
                  <span className="shrink-0 text-xs whitespace-nowrap text-text-muted tabular-nums">
                    {!entry.available
                      ? t('playlist.unavailable')
                      : entry.durationSec !== undefined && formatDuration(entry.durationSec)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
        {count === 0 && <p className="mr-auto text-text-muted">{t('playlist.noneSelected')}</p>}
        <Button onClick={close}>
          {t('action.cancel')}
        </Button>
        <Button variant="primary" autoFocus disabled={count === 0 || busy} onClick={() => void add()}>
          {t('playlist.add', { count })}
        </Button>
      </div>
    </section>
  )
}

