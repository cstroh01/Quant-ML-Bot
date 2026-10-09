import { expect, test } from 'vitest'
import { add } from './sample'

test('add', () => {
  expect(add(2, 3), 'SAMPLE ADD').toBe(5)
})
