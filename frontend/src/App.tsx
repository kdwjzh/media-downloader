import { AppUpdateDialog } from './components/AppUpdateDialog'
import { ConfirmCloseDialog } from './components/ConfirmCloseDialog'
import { ErrorBoundary } from './components/ErrorBoundary'
import { NavRail } from './components/NavRail'
import { LiveRegion, Toast } from './components/Notices'
import { HistoryPage } from './pages/HistoryPage'
import { MainPage } from './pages/MainPage'
import { SettingsPage } from './pages/SettingsPage'
import { usePage } from './stores/page'

// Two layers of error boundaries: each screen has its own, so one that breaks leaves the
// navigation, the other screen and the close question working; the outer one catches the
// rest (design step 4). Every screen stays mounted and only the others are hidden, so
// switching keeps what was on the main screen (decisions/0015).
export default function App() {
  const page = usePage((s) => s.page)
  return (
    <ErrorBoundary>
      <div className="flex h-screen">
        <NavRail />
        <div hidden={page !== 'downloads'} className="flex min-w-0 flex-1">
          <ErrorBoundary>
            <MainPage />
          </ErrorBoundary>
        </div>
        <div hidden={page !== 'history'} className="flex min-w-0 flex-1">
          <ErrorBoundary>
            <HistoryPage />
          </ErrorBoundary>
        </div>
        <div hidden={page !== 'settings'} className="flex min-w-0 flex-1">
          <ErrorBoundary>
            <SettingsPage />
          </ErrorBoundary>
        </div>
      </div>
      <Toast />
      <LiveRegion />
      <AppUpdateDialog />
      <ConfirmCloseDialog />
    </ErrorBoundary>
  )
}
