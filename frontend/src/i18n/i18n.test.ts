import { expect, test } from 'vitest'
import en from './en.json'
import zhTW from './zh-TW.json'

function keys(node: unknown, prefix = ''): string[] {
  if (typeof node !== 'object' || node === null) return [prefix]
  return Object.entries(node).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k))
}

test('zh-TW and en define exactly the same keys', () => {
  expect(keys(zhTW).sort()).toEqual(keys(en).sort())
})
