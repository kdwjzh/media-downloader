import { expect, test } from 'vitest'
import { looksLikeUrl } from './paste'

test('looksLikeUrl keeps out what clearly is not a URL, and leaves the rest to the backend', () => {
  expect(looksLikeUrl(' https://www.youtube.com/watch?v=jNQXAC9IVRw \n')).toBe(true)
  expect(looksLikeUrl('youtu.be/jNQXAC9IVRw')).toBe(true)
  expect(looksLikeUrl('example.com')).toBe(true) // unsupportedSite is the backend's call
  expect(looksLikeUrl('')).toBe(false)
  expect(looksLikeUrl('just some words')).toBe(false)
  expect(looksLikeUrl('https://a.com\nhttps://b.com')).toBe(false)
  expect(looksLikeUrl('localhost')).toBe(false)
  expect(looksLikeUrl(`https://a.com/${'x'.repeat(2048)}`)).toBe(false)
})
