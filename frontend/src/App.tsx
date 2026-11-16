import { ConfirmCloseDialog } from './components/ConfirmCloseDialog'
import { ErrorBoundary } from './components/ErrorBoundary'
import { NavRail } from './components/NavRail'
import { LiveRegion, Toast } from './components/Notices'
import { MainPage } from './pages/MainPage'

// Two error boundaries: the inner one keeps the navigation and the close question working
// when the page breaks; the outer one catches the rest (design step 4).
export default function App() {
  return (
    <ErrorBoundary>
      <div className="flex h-screen">
        <NavRail current="downloads" />
        <ErrorBoundary>
          <MainPage />
        </ErrorBoundary>
      </div>
      <Toast />
      <LiveRegion />
      <ConfirmCloseDialog />
    </ErrorBoundary>
  )
}
