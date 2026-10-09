// Spec 047 T005 Rule 12: a deliberately failing case. CI requires this run to FAIL.
import { expect, test } from 'vitest'

test('planted failure', () => {
  expect(1 + 1, 'T005 PLANTED').toBe(3)
})
