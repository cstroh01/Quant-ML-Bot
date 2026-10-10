// Mutation-helper fixture: every assertion passes, then a suite hook errors. EXAMPLE — NOT A RESULT.
import { afterAll, expect, test } from 'vitest'

test('hook fixture passing case', () => {
  expect(1 + 1, 'HOOK PASS').toBe(2)
})

afterAll(() => {
  throw new Error('SAMPLE ADD hook failure')
})
