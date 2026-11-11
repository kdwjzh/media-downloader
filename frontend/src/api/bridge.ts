// The only place in the frontend that talks to the pywebview bridge.

interface BridgeApi {
  ping(): Promise<string>
}

declare global {
  interface Window {
    pywebview?: { api?: BridgeApi }
  }
}

const READY_TIMEOUT_MS = 5000

function bridge(): Promise<BridgeApi> {
  const api = window.pywebview?.api
  if (api) return Promise.resolve(api)
  return new Promise((resolve, reject) => {
    // Never fires in a plain browser, so give up instead of waiting forever.
    const timer = setTimeout(() => reject(new Error('bridge unavailable')), READY_TIMEOUT_MS)
    window.addEventListener(
      'pywebviewready',
      () => {
        clearTimeout(timer)
        const ready = window.pywebview?.api
        if (ready) resolve(ready)
        else reject(new Error('bridge unavailable'))
      },
      { once: true },
    )
  })
}

export async function ping(): Promise<string> {
  return (await bridge()).ping()
}
