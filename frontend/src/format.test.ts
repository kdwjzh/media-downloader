import { expect, test } from 'vitest'
import { formatBytes, formatDuration } from './format'

const MB = 1024 * 1024

test('formatBytes picks a unit that keeps the number short', () => {
  expect(formatBytes(512 * 1024)).toBe('512 KB')
  expect(formatBytes(1.68 * MB)).toBe('1.7 MB')
  expect(formatBytes(966 * MB)).toBe('966 MB')
  expect(formatBytes(1536 * MB)).toBe('1.5 GB')
})

test('formatDuration shows hours only when there are any', () => {
  expect(formatDuration(19)).toBe('0:19')
  expect(formatDuration(241)).toBe('4:01')
  expect(formatDuration(3600)).toBe('1:00:00')
})
