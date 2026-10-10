// Mutation-helper fixture: a passing test beside a broken import. EXAMPLE — NOT A RESULT.
import { expect, test } from 'vitest'

test('broken fixture passing case', () => {
  expect(2 + 2, 'BROKEN PASS').toBe(4)
})
