import { ClockCounterClockwise, DownloadSimple, GearSix } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { type Page, showPage, usePage } from '../stores/page'
import { FINISHED, useQueue } from '../stores/queue'
import { useUpdates } from '../stores/updates'

const items = [
  { key: 'downloads', Icon: DownloadSimple },
  { key: 'history', Icon: ClockCounterClockwise },
  { key: 'settings', Icon: GearSix },
] as const satisfies readonly { key: Page; Icon: unknown }[]

export function NavRail() {
  const { t } = useTranslation()
  const current = usePage((s) => s.page)
  // A state, not a notice: shown as long as a newer version exists (decisions/0016).
  const updateAvailable = useUpdates((s) => s.latestVersion !== undefined)
  // Seen from any screen: downloads still running while the history is open (decisions/0015).
  const unfinished = useQueue((s) => s.items.filter((item) => !FINISHED.has(item.status)).length)
  return (
    <nav aria-label={t('nav.label')} className="flex w-22 shrink-0 flex-col gap-1 px-2 py-6">
      {items.map(({ key, Icon }) => {
        const active = key === current
        return (
          <button
            key={key}
            type="button"
            aria-current={active ? 'page' : undefined}
            onClick={() => showPage(key)}
            className={`relative flex cursor-pointer flex-col items-center gap-1 rounded-lg py-2 text-xs transition-colors duration-150 ${
              active ? 'bg-accent-soft font-medium text-accent' : 'text-text-muted hover:bg-accent-soft hover:text-text'
            }`}
          >
            <Icon size={20} aria-hidden="true" />
            {t(`nav.${key}`)}
            {key === 'downloads' && unfinished > 0 && (
              <>
                {/* Not a live region: the queue's own messages already say what changed. */}
                <span
                  aria-hidden="true"
                  className="absolute top-0.5 right-2.5 h-4 min-w-4.5 rounded-full bg-accent px-1 font-display text-xs leading-4 font-semibold text-on-accent tabular-nums"
                >
                  {unfinished > 99 ? '99+' : unfinished}
                </span>
                <span className="sr-only">{t('nav.unfinished', { count: unfinished })}</span>
              </>
            )}
            {key === 'settings' && updateAvailable && (
              <span
                role="img"
                aria-label={t('nav.updateAvailable')}
                title={t('nav.updateAvailable')}
                className="absolute top-1.5 right-4 size-2 rounded-full bg-accent"
              />
            )}
          </button>
        )
      })}
    </nav>
  )
}
