// Which screen is showing. Every screen stays mounted and only the others are hidden, so
// a preview still looking, half-ticked playlist or scrolled queue are there on return.

import { create } from 'zustand'

export type Page = 'downloads' | 'history' | 'settings'

interface PageState {
  page: Page
  /** Goes up each time the URL box should take focus once the main screen shows. */
  urlFocus: number
}

export const usePage = create<PageState>(() => ({ page: 'downloads', urlFocus: 0 }))

export function showPage(page: Page): void {
  usePage.setState({ page })
}

/** To the main screen with focus in the URL box ("Go to Downloads", a paste elsewhere). */
export function goToUrlBox(): void {
  usePage.setState((s) => ({ page: 'downloads', urlFocus: s.urlFocus + 1 }))
}
