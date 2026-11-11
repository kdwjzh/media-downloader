import { expect, test } from 'vitest'
import en from '../src/i18n/en.json'
import zhTW from '../src/i18n/zh-TW.json'

function keys(node: object, prefix = ''): string[] {
  return Object.entries(node).flatMap(([key, value]) =>
    typeof value === 'object' && value !== null ? keys(value, `${prefix}${key}.`) : [`${prefix}${key}`],
  )
}

test('zh-TW and en have the same keys', () => {
  expect(keys(zhTW).sort()).toEqual(keys(en).sort())
})
