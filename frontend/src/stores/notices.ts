// Short messages the main screen hands to people: a toast to see, a line for screen
// readers to hear. Both hold language-file keys; the components translate them.

import { create } from 'zustand'

export interface Notice {
  id: number
  key: string
  params?: Record<string, string | number>
}

const KEEP_SPOKEN = 3

interface NoticesState {
  toast?: Notice
  spoken: Notice[]
}

export const useNotices = create<NoticesState>(() => ({ spoken: [] }))

let next = 0

/** One toast at a time: a new one replaces the one on screen. */
export function showToast(key: string, params?: Notice['params']): void {
  useNotices.setState({ toast: { id: ++next, key, params } })
}

export function hideToast(id: number): void {
  if (useNotices.getState().toast?.id === id) useNotices.setState({ toast: undefined })
}

/** Read out by the polite live region. Only the last few stay in the page. */
export function announce(key: string, params?: Notice['params']): void {
  useNotices.setState((s) => ({ spoken: [...s.spoken, { id: ++next, key, params }].slice(-KEEP_SPOKEN) }))
}
