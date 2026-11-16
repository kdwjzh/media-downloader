// Development only (stage 4a): shows that the pipe between the page and Python works.
// App.tsx loads it behind import.meta.env.DEV, so a production build leaves it out entirely.
// Stage 4b deletes this folder. Like src/mock, its labels are deliberately not translated.

import { useEffect, useState } from 'react'
import { type DataEvent, addToQueue, getQueue, lookup, onCloseRequested, onEvent } from '../api'

const MAX_EVENTS = 200
const button = 'h-7 rounded border border-border bg-surface px-2 hover:bg-accent-soft'

function show(value: unknown): string {
  return JSON.stringify(value, null, 1)
}

export default function BridgePanel() {
  const [open, setOpen] = useState(true)
  const [url, setUrl] = useState('https://www.youtube.com/watch?v=jNQXAC9IVRw')
  const [reply, setReply] = useState('')
  const [events, setEvents] = useState<{ at: string; event: DataEvent | { type: 'closeRequested' } }[]>([])

  useEffect(() => {
    const at = () => new Date().toLocaleTimeString()
    const keep = (event: DataEvent | { type: 'closeRequested' }) =>
      setEvents((list) => [{ at: at(), event }, ...list].slice(0, MAX_EVENTS))
    const stopEvents = onEvent(keep)
    // Listening here means closing with tasks running no longer closes by itself: the
    // panel offers the confirmation 4b will draw properly.
    const stopClose = onCloseRequested(() => keep({ type: 'closeRequested' }))
    return () => {
      stopEvents()
      stopClose()
    }
  }, [])

  async function run(label: string, work: () => Promise<unknown>) {
    setReply(`${label}…`)
    const started = performance.now()
    const result = await work()
    setReply(`${label} (${Math.round(performance.now() - started)} ms)\n${show(result)}`)
  }

  if (!open) {
    return (
      <button className={`${button} fixed right-2 bottom-2 z-50 text-xs`} onClick={() => setOpen(true)}>
        Bridge
      </button>
    )
  }
  return (
    <section className="fixed inset-x-2 bottom-2 z-50 flex h-[45vh] flex-col gap-2 rounded border border-dashed border-border bg-surface p-2 text-xs text-text shadow-lg">
      <div className="flex flex-wrap items-center gap-2">
        <strong>Bridge (dev)</strong>
        <input
          className="h-7 min-w-0 flex-1 rounded border border-border px-2"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          aria-label="URL"
        />
        <button className={button} onClick={() => void run('lookup', () => lookup(url))}>
          lookup
        </button>
        <button className={button} onClick={() => void run('add_to_queue mp3 128', () => addToQueue([url], 'mp3', 128))}>
          add MP3 128
        </button>
        <button className={button} onClick={() => void run('get_queue', getQueue)}>
          get_queue
        </button>
        <button className={button} onClick={() => setEvents([])}>
          clear events
        </button>
        <button className={button} onClick={() => setOpen(false)}>
          hide
        </button>
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-2 gap-2">
        <pre className="overflow-auto rounded bg-bg p-2 whitespace-pre-wrap" aria-label="Reply">
          {reply || 'Reply of the last command'}
        </pre>
        <ol className="overflow-auto rounded bg-bg p-2" aria-label="Events" aria-live="off">
          {events.length === 0 && <li>Events, newest first</li>}
          {events.map(({ at, event }, i) => (
            <li key={events.length - i} className="border-b border-divider py-1">
              <span className="text-text-muted">{at}</span> <strong>{event.type}</strong>
              <pre className="whitespace-pre-wrap">{show(event)}</pre>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
