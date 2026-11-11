import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ping } from './api/bridge'

type Status = 'connecting' | 'connected' | 'failed'

export default function App() {
  const { t } = useTranslation()
  const [status, setStatus] = useState<Status>('connecting')

  useEffect(() => {
    ping().then(
      (reply) => setStatus(reply === 'pong' ? 'connected' : 'failed'),
      () => setStatus('failed'),
    )
  }, [])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-3xl font-semibold">{t('app.name')}</h1>
      <p role="status">{t(`backend.${status}`)}</p>
    </main>
  )
}
