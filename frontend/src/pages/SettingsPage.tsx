import { CheckCircle, Warning } from '@phosphor-icons/react'
import { type ReactNode, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../components/Button'
import { ProgressBar } from '../components/QueueRow'
import { Segmented } from '../components/Segmented'
import { formatBytes, shortenPath } from '../format'
import { usePage } from '../stores/page'
import { openLog } from '../stores/queue'
import { changeSettings, chooseFolder, useSettings } from '../stores/settings'
import {
  cancelAppUpdate,
  installAppUpdate,
  loadAbout,
  openLink,
  openLogFolder,
  startAppUpdate,
  updateEngine,
  useUpdates,
} from '../stores/updates'
import { CONCURRENT_CHOICES, type Language, MP3_BITRATES, MP4_HEIGHTS, type OnDuplicate, type Settings } from '../types'

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId()
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2">
      <h2 id={id} className="font-medium text-text-muted">
        {title}
      </h2>
      <div className="divide-y divide-divider rounded-[10px] bg-surface">{children}</div>
    </section>
  )
}

/** Label 160 on the left, the control on the right (pages/settings.md); `below` goes under
 *  the control. The narrowest window still fits every row this way (decisions/0016). `wide`
 *  puts the control under the label across the whole row (the components table). */
function Row(props: { label: ReactNode; labelId?: string; htmlFor?: string; children: ReactNode; below?: ReactNode; wide?: boolean }) {
  const { label, labelId, htmlFor, children, below, wide = false } = props
  const cls = 'font-medium'
  return (
    <div className="grid min-h-14 grid-cols-[160px_minmax(0,1fr)] items-center gap-x-3 gap-y-1 p-3">
      {htmlFor ? (
        <label htmlFor={htmlFor} className={cls}>
          {label}
        </label>
      ) : (
        <span id={labelId} className={cls}>
          {label}
        </span>
      )}
      <div className={`flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 ${wide ? 'col-span-2' : ''}`}>{children}</div>
      {below && <div className="col-start-2 text-xs">{below}</div>}
    </div>
  )
}

const Skeleton = () => (
  <span aria-hidden="true" className="inline-block h-3 w-22 animate-skeleton rounded bg-divider motion-reduce:animate-none" />
)

function FolderRow({ dir }: { dir: string }) {
  const { t } = useTranslation()
  const labelId = useId()
  const pathId = useId()
  const failed = useSettings((s) => s.folderFailed)
  const shown = useRef<HTMLSpanElement>(null)
  const [focused, setFocused] = useState(false)
  const [cut, setCut] = useState(false)
  useLayoutEffect(() => {
    const el = shown.current!
    const fit = () => {
      el.textContent = shortenPath(dir, (text) => {
        el.textContent = text
        return el.scrollWidth <= el.clientWidth
      })
      setCut(el.textContent !== dir)
    }
    fit()
    const resize = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(fit)
    resize?.observe(el)
    return () => resize?.disconnect()
  }, [dir])
  return (
    <div
      onFocus={() => setFocused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setFocused(false)
      }}
    >
      <Row
        label={t('settings.folder')}
        labelId={labelId}
        below={
          <>
            {/* Keyboard users never see a title attribute: the whole path while focus is here. */}
            {focused && cut && (
              <p aria-hidden="true" className="text-text-muted wrap-anywhere">
                {dir}
              </p>
            )}
            {failed && (
              <p role="alert" className="flex items-center gap-1 font-medium text-danger">
                <Warning size={16} aria-hidden="true" className="shrink-0" />
                {t('settings.folderNotWritable')}
              </p>
            )}
          </>
        }
      >
        {/* Filled in by shortenPath(); React leaves its text alone. */}
        <span ref={shown} aria-hidden="true" title={dir} className="min-w-0 flex-1 overflow-hidden whitespace-nowrap" />
        <span id={pathId} className="sr-only">
          {dir}
        </span>
        <Button aria-describedby={`${labelId} ${pathId}`} onClick={() => void chooseFolder()}>
          {t('settings.changeFolder')}
        </Button>
      </Row>
    </div>
  )
}

function DownloadSection({ settings }: { settings: Settings }) {
  const { t } = useTranslation()
  const concurrentId = useId()
  const duplicateId = useId()
  const warningId = useId()
  const overwrite = settings.onDuplicate === 'overwrite'
  const choices: [OnDuplicate, string][] = [
    ['skip', t('settings.duplicateSkip')],
    ['overwrite', t('settings.duplicateOverwrite')],
    ['rename', t('settings.duplicateRename')],
  ]
  return (
    <Section title={t('settings.download')}>
      <FolderRow dir={settings.downloadDir} />
      <Row label={t('settings.concurrent')} labelId={concurrentId}>
        <Segmented
          labelledBy={concurrentId}
          options={CONCURRENT_CHOICES.map((n) => ({ value: n, label: String(n) }))}
          value={settings.maxConcurrent}
          onChange={(n) => void changeSettings({ maxConcurrent: n })}
        />
      </Row>
      <Row
        label={t('settings.duplicate')}
        labelId={duplicateId}
        below={
          overwrite && (
            <p id={warningId} className="text-danger">
              {t('settings.overwriteWarning')}
            </p>
          )
        }
      >
        <div
          role="radiogroup"
          aria-labelledby={duplicateId}
          aria-describedby={overwrite ? warningId : undefined}
          className="flex flex-wrap gap-x-4"
        >
          {choices.map(([value, label]) => (
            <label key={value} className="flex min-h-8 cursor-pointer items-center gap-1.5 whitespace-nowrap">
              <input
                type="radio"
                name={duplicateId}
                className="size-4 accent-accent"
                checked={settings.onDuplicate === value}
                onChange={() => void changeSettings({ onDuplicate: value })}
              />
              {label}
            </label>
          ))}
        </div>
      </Row>
    </Section>
  )
}

const selectCls = 'h-9 min-w-40 rounded-lg border border-border bg-surface px-2'

function DefaultsSection({ settings }: { settings: Settings }) {
  const { t } = useTranslation()
  const formatId = useId()
  const mp3Id = useId()
  const mp4Id = useId()
  return (
    <Section title={t('settings.defaults')}>
      <Row label={t('format.label')} labelId={formatId}>
        <Segmented
          labelledBy={formatId}
          options={[
            { value: 'mp3', label: t('format.mp3') },
            { value: 'mp4', label: t('format.mp4') },
          ]}
          value={settings.format}
          onChange={(format) => void changeSettings({ format })}
        />
      </Row>
      <Row label={t('settings.mp3Quality')} htmlFor={mp3Id}>
        <select
          id={mp3Id}
          className={selectCls}
          value={settings.mp3Bitrate}
          onChange={(e) => void changeSettings({ mp3Bitrate: Number(e.target.value) })}
        >
          {[...MP3_BITRATES].reverse().map((n) => (
            <option key={n} value={n}>
              {t('quality.kbps', { n })}
            </option>
          ))}
        </select>
      </Row>
      <Row label={t('settings.mp4Quality')} htmlFor={mp4Id} below={<p className="text-text-muted">{t('settings.defaultsHint')}</p>}>
        <select
          id={mp4Id}
          className={selectCls}
          value={settings.mp4Height}
          onChange={(e) => void changeSettings({ mp4Height: Number(e.target.value) })}
        >
          {MP4_HEIGHTS.map((n) => (
            <option key={n} value={n}>
              {t('quality.upTo', { n })}
            </option>
          ))}
        </select>
      </Row>
    </Section>
  )
}

function InterfaceSection({ settings }: { settings: Settings }) {
  const { t } = useTranslation()
  const id = useId()
  return (
    <Section title={t('settings.interface')}>
      <Row label={t('settings.language')} htmlFor={id}>
        <select
          id={id}
          className={selectCls}
          value={settings.language}
          onChange={(e) => void changeSettings({ language: e.target.value as Language })}
        >
          <option value="system">{t('settings.languageSystem')}</option>
          {/* Each language in its own words, so a screen reader speaks it in that language. */}
          <option value="zh-TW" lang="zh-TW">
            {t('settings.languageZhTW')}
          </option>
          <option value="en" lang="en">
            {t('settings.languageEn')}
          </option>
        </select>
      </Row>
    </Section>
  )
}

const APP_FAILED: Record<string, string> = {
  network: 'appUpdate.failedNetwork',
  checksumMismatch: 'appUpdate.failedChecksum',
}

/** The app's own row: "Update now", then its progress, check, install or failure. One
 *  button element throughout, so focus stays on it as its job changes (decisions/0019). */
function AppRow({ version }: { version: ReactNode }) {
  const { t } = useTranslation()
  const labelId = useId()
  const { latestVersion, app } = useUpdates()
  const { stage, receivedBytes = 0, totalBytes, error } = app
  const busy = stage === 'downloading' || stage === 'verifying'
  const percent = totalBytes ? Math.min(100, Math.floor((receivedBytes / totalBytes) * 100)) : undefined
  const action = busy
    ? { label: t('action.cancel'), run: cancelAppUpdate }
    : stage === 'ready' || stage === 'installing'
      ? { label: t('appUpdate.installNow'), run: installAppUpdate }
      : { label: stage === 'failed' ? t('action.retry') : t('appUpdate.updateNow'), run: startAppUpdate }
  let below: ReactNode = null
  if (stage === 'downloading') {
    const label =
      percent === undefined
        ? t('appUpdate.downloadingNoTotal', { received: formatBytes(receivedBytes) })
        : t('appUpdate.downloading', { percent, received: formatBytes(receivedBytes), total: formatBytes(totalBytes ?? 0) })
    below = (
      <div className="flex flex-col gap-1">
        <ProgressBar percent={percent} label={t('appUpdate.progressLabel')} />
        <p className="tabular-nums">{label}</p>
        <p className="text-text-muted">{t('appUpdate.closesAfter')}</p>
      </div>
    )
  } else if (stage === 'verifying') {
    below = (
      <div className="flex flex-col gap-1">
        <ProgressBar label={t('appUpdate.progressLabel')} />
        <p>{t('appUpdate.verifying')}</p>
      </div>
    )
  } else if (stage === 'ready') {
    below = <p>{t('appUpdate.ready')}</p>
  } else if (stage === 'installing') {
    below = <p>{t('appUpdate.installing')}</p>
  } else if (stage === 'failed') {
    below = (
      <div className="flex flex-wrap items-center gap-x-2">
        <p className="flex items-center gap-1 font-medium text-danger">
          <Warning size={16} aria-hidden="true" className="shrink-0" />
          {t(APP_FAILED[error ?? ''] ?? 'appUpdate.failedUnknown')}
        </p>
        {error !== 'network' && error !== 'checksumMismatch' && (
          <Button variant="text" onClick={() => void openLog()}>
            {t('action.openLog')}
          </Button>
        )}
      </div>
    )
  }
  return (
    <Row label={t('app.name')} labelId={labelId} below={latestVersion && <div aria-live="polite">{below}</div>}>
      {version}
      {latestVersion && (
        <>
          <span>{t('settings.newVersion', { version: latestVersion })}</span>
          {/* aria-disabled, not disabled: a disabled button drops keyboard focus to the page. */}
          <Button
            aria-disabled={stage === 'installing' || undefined}
            aria-describedby={labelId}
            className="aria-disabled:pointer-events-none aria-disabled:opacity-45"
            onClick={() => void action.run()}
          >
            {action.label}
          </Button>
          {stage === 'failed' && <Button onClick={() => void openLink('releasePage')}>{t('settings.getUpdate')}</Button>}
        </>
      )}
    </Row>
  )
}

function UpdatesSection() {
  const { t } = useTranslation()
  const ytdlpId = useId()
  const { about, aboutStatus, engine } = useUpdates()
  const checking = engine.state === 'checking'
  const failed = engine.state === 'failed'
  // After an update the new version is known before the About list is read again.
  const ytdlp = engine.state === 'updated' ? engine.version : about?.components.find((c) => c.name === 'yt-dlp')?.version
  const version = (v: string | undefined) => (aboutStatus === 'loading' && !v ? <Skeleton /> : <span className="tabular-nums">{v ?? '—'}</span>)
  return (
    <Section title={t('settings.updates')}>
      <AppRow version={version(about?.appVersion)} />
      <Row
        label="yt-dlp"
        labelId={ytdlpId}
        below={
          <div aria-live="polite" className="flex flex-wrap items-center gap-x-2">
            {checking && <p className="text-text-muted">{t('settings.checkingSlow')}</p>}
            {(engine.state === 'latest' || engine.state === 'updated') && (
              <p className="flex items-center gap-1 text-success">
                <CheckCircle size={16} aria-hidden="true" className="shrink-0" />
                {engine.state === 'latest' ? t('settings.upToDate') : t('settings.updatedTo', { version: engine.version })}
              </p>
            )}
            {failed && (
              <p className="flex items-center gap-1 font-medium text-danger">
                <Warning size={16} aria-hidden="true" className="shrink-0" />
                {t(engine.code === 'network' ? 'settings.updateFailed' : 'settings.updateFailedUnknown')}
              </p>
            )}
            {failed && engine.code === 'unknown' && (
              <Button variant="text" onClick={() => void openLog()}>
                {t('action.openLog')}
              </Button>
            )}
          </div>
        }
      >
        {version(ytdlp)}
        {/* aria-disabled, not disabled: a disabled button drops keyboard focus to the page. */}
        <Button
          aria-disabled={checking || undefined}
          aria-describedby={ytdlpId}
          className="aria-disabled:pointer-events-none aria-disabled:opacity-45"
          onClick={() => void updateEngine()}
        >
          {checking ? t('settings.checking') : failed ? t('action.retry') : t('settings.checkUpdate')}
        </Button>
      </Row>
    </Section>
  )
}

function AboutSection() {
  const { t } = useTranslation()
  const { about, aboutStatus } = useUpdates()
  return (
    <Section title={t('settings.about')}>
      <Row label={t('app.name')}>
        {about ? <span className="tabular-nums">{t('settings.appLicense', { version: about.appVersion })}</span> : <Skeleton />}
      </Row>
      <Row label={t('settings.components')} wide>
        {aboutStatus === 'failed' ? (
          <>
            <p className="text-danger">{t('settings.aboutFailed')}</p>
            <Button onClick={() => void loadAbout(true)}>{t('action.retry')}</Button>
          </>
        ) : about ? (
          <table className="w-full text-xs leading-4">
            <thead className="text-left text-text-muted">
              <tr>
                <th className="pb-1 font-normal">{t('settings.componentName')}</th>
                <th className="pb-1 font-normal">{t('settings.license')}</th>
                <th className="pb-1 font-normal">{t('settings.version')}</th>
              </tr>
            </thead>
            <tbody>
              {about.components.map((c) => (
                <tr key={c.name}>
                  <td className="py-0.5 pr-3 whitespace-nowrap">{c.name}</td>
                  <td className="py-0.5 pr-3 whitespace-nowrap">{c.license}</td>
                  <td className="py-0.5 tabular-nums wrap-anywhere">{c.version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div aria-hidden="true" className="flex w-full flex-col gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <span key={n} className="h-3 w-4/5 animate-skeleton rounded bg-divider motion-reduce:animate-none" />
            ))}
          </div>
        )}
      </Row>
      <Row label="">
        <Button onClick={() => void openLink('sourceCode')}>{t('settings.sourceCode')}</Button>
        <Button onClick={() => void openLogFolder()}>{t('settings.openLogFolder')}</Button>
      </Row>
    </Section>
  )
}

/** The only screen whose page scrolls (pages/settings.md). Every change takes effect at once. */
export function SettingsPage() {
  const { t } = useTranslation()
  const showing = usePage((s) => s.page === 'settings')
  const settings = useSettings((s) => s.settings)

  // Read the first time the screen shows: it starts three programs (decisions/0016).
  useEffect(() => {
    if (showing) void loadAbout()
  }, [showing])

  return (
    <main className="min-h-0 min-w-0 flex-1 overflow-y-auto p-6 pl-2">
      <div className="flex max-w-160 flex-col gap-4">
        <h1 className="font-display text-xl font-semibold">{t('settings.title')}</h1>
        {settings && (
          <>
            <DownloadSection settings={settings} />
            <DefaultsSection settings={settings} />
            <InterfaceSection settings={settings} />
          </>
        )}
        <UpdatesSection />
        <AboutSection />
      </div>
    </main>
  )
}
