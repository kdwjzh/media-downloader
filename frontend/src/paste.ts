// Ctrl+V anywhere looks up what was copied, so stray text must not count: pasting would
// also add the previous preview to the queue (decisions/0006). The backend still decides
// what is really a valid URL; this only keeps out what clearly is not one.

const MAX_LENGTH = 2048

export function looksLikeUrl(text: string): boolean {
  const s = text.trim()
  return s.length > 0 && s.length <= MAX_LENGTH && !/\s/.test(s) && s.includes('.')
}

/** Text fields keep their own paste; only the empty URL box takes part in looking up. */
export function isOtherTextField(el: Element | null, urlBox: Element | null): boolean {
  if (!el || el === urlBox) return false
  return el.matches('input, textarea, select, [contenteditable=""], [contenteditable="true"]')
}
