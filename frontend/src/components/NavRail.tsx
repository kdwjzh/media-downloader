import { ClockCounterClockwise, DownloadSimple, GearSix } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'

const items = [
  { key: 'downloads', Icon: DownloadSimple },
  { key: 'history', Icon: ClockCounterClockwise },
  { key: 'settings', Icon: GearSix },
] as const

interface Props {
  current: (typeof items)[number]['key']
  updateAvailable?: boolean
}

export function NavRail({ current, updateAvailable = false }: Props) {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('nav.label')} className="flex w-22 shrink-0 flex-col gap-1 px-2 py-6">
      {items.map(({ key, Icon }) => {
        const active = key === current
        return (
          <button
            key={key}
            type="button"
            aria-current={active ? 'page' : undefined}
            className={`relative flex cursor-pointer flex-col items-center gap-1 rounded-lg py-2 text-xs transition-colors duration-150 ${
              active ? 'bg-accent-soft font-medium text-accent' : 'text-text-muted hover:bg-accent-soft hover:text-text'
            }`}
          >
            <Icon size={20} aria-hidden="true" />
            {t(`nav.${key}`)}
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
