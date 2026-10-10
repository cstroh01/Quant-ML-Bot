// Mutation-helper fixture: the assertion passes, then an unhandled rejection. EXAMPLE — NOT A RESULT.
import { expect, test } from 'vitest'

test('unhandled fixture passing case', async () => {
  void Promise.reject(new Error('SAMPLE ADD unhandled'))
  await new Promise((resolve) => setTimeout(resolve, 20))
  expect(1, 'UNHANDLED PASS').toBe(1)
})
