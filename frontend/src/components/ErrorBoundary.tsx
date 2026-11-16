import { Warning } from '@phosphor-icons/react'
import { Component, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from './Button'

function Crashed() {
  const { t } = useTranslation()
  return (
    <div role="alert" className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <Warning size={32} aria-hidden="true" className="text-danger" />
      <h2 className="text-base font-medium">{t('crash.title')}</h2>
      <p className="max-w-md text-text-muted">{t('crash.body')}</p>
      {/* The queue lives in the backend: a fresh page gets it back with getQueue(). */}
      <Button variant="primary" className="mt-2" onClick={() => window.location.reload()}>
        {t('crash.reload')}
      </Button>
    </div>
  )
}

/** One part of the screen breaking leaves the rest working (design step 4). */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: unknown) {
    // shortcut: page errors only reach the dev tools' console, not the app's log file;
    // sending them there needs a new bridge command.
    console.error(error)
  }

  render() {
    return this.state.failed ? <Crashed /> : this.props.children
  }
}
