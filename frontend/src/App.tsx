import { Suspense, lazy, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ping } from './api'
import { NavRail } from './components/NavRail'
import { StateSwitcher } from './mock/StateSwitcher'
import { type PreviewKey, type QueueKey, previews, queues } from './mock/sample'
import { MainPage } from './pages/MainPage'

type Status = 'connecting' | 'connected' | 'failed'

// Stage 4a check panel. DEV is false in a production build, so the import is dropped with it.
const BridgePanel = import.meta.env.DEV ? lazy(() => import('./dev/BridgePanel')) : null

// Stage 2 static sample: the screen is real, the data comes from src/mock.
export default function App() {
  const { t } = useTranslation()
  const [status, setStatus] = useState<Status>('connecting')
  const [preview, setPreview] = useState<PreviewKey>('none')
  const [queue, setQueue] = useState<QueueKey>('empty')

  useEffect(() => {
    void ping().then((reply) => setStatus(reply.ok && reply.data === 'pong' ? 'connected' : 'failed'))
  }, [])

  return (
    <div className="flex h-screen flex-col">
      <StateSwitcher preview={preview} queue={queue} onPreview={setPreview} onQueue={setQueue}>
        <span role="status">{t(`backend.${status}`)}</span>
      </StateSwitcher>
      <div className="flex min-h-0 flex-1">
        <NavRail current="downloads" updateAvailable />
        <MainPage
          preview={previews[preview]}
          queue={queues[queue]}
          defaults={{ format: 'mp3', bitrate: 320, height: 1080 }}
        />
      </div>
      {BridgePanel && (
        <Suspense>
          <BridgePanel />
        </Suspense>
      )}
    </div>
  )
}
