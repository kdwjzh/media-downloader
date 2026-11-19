import { useTranslation } from 'react-i18next'
import { FINISHED, useQueue } from '../stores/queue'
import { confirmInstall, keepDownloading, useUpdates } from '../stores/updates'
import { ConfirmDialog } from './ConfirmDialog'

/** Asks before an app update stops unfinished downloads (decisions/0019). Mounted beside
 *  the screens, not in one: the update may become ready while another screen shows. */
export function AppUpdateDialog() {
  const { t } = useTranslation()
  const open = useUpdates((s) => s.askInstall)
  const count = useQueue((s) => s.items.filter((item) => !FINISHED.has(item.status)).length)
  return (
    <ConfirmDialog
      open={open}
      title={t('appUpdate.confirmTitle', { count })}
      body={t('appUpdate.confirmBody')}
      keepLabel={t('close.keep')}
      confirmLabel={t('appUpdate.confirm')}
      onKeep={keepDownloading}
      onConfirm={() => void confirmInstall()}
    />
  )
}
