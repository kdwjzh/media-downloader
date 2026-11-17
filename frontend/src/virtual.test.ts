import { expect, test } from 'vitest'
import { rowsToDraw, scrollToRow } from './virtual'

test('a list of 100 rows or fewer draws every row', () => {
  expect(rowsToDraw(100, 56, 5000, 300)).toHaveLength(100)
  expect(rowsToDraw(0, 56, 0, 300)).toEqual([])
})

test('a long list draws the rows in view plus a margin', () => {
  // 300 px of 56 px rows starting at row 1000: rows 1000-1005 are in view.
  const rows = rowsToDraw(1700, 56, 56 * 1000, 300)
  expect(rows[0]).toBe(994)
  expect(rows.at(-1)).toBe(1011)
})

test('the margin stops at both ends', () => {
  expect(rowsToDraw(1700, 56, 0, 300)[0]).toBe(0)
  expect(rowsToDraw(1700, 56, 56 * 1695, 300).at(-1)).toBe(1699)
})

test('the row holding focus is drawn even when scrolled away', () => {
  expect(rowsToDraw(1700, 56, 56 * 1000, 300, 3)).toContain(3)
  expect(rowsToDraw(1700, 56, 0, 300, 1500)).toContain(1500)
  expect(rowsToDraw(1700, 56, 0, 300, 2).filter((i) => i === 2)).toHaveLength(1)
})

test('scrollToRow moves only as far as needed', () => {
  const el = { scrollTop: 560, clientHeight: 280 } as HTMLElement
  scrollToRow(el, 12, 56) // already in view
  expect(el.scrollTop).toBe(560)
  scrollToRow(el, 5, 56) // above: its top lines up with the view's
  expect(el.scrollTop).toBe(280)
  scrollToRow(el, 20, 56) // below: its bottom lines up with the view's
  expect(el.scrollTop).toBe(56 * 21 - 280)
})
