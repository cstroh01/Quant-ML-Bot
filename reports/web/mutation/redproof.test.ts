// Spec 047 T005 Rule 12: the strict red proof CI runs by name. EXAMPLE — NOT A RESULT.
// Passing means the planted test was collected and failed on its own assertion, with no
// runner, import, collection or unhandled error. Any other nonzero exit is not red proof.
import { expect, test } from 'vitest'
import { plantedRed } from './mutate'

const planted = 'mutation/planted/vitest.config.ts'

test('the planted web test turns the runner red on its named assertion', () => {
  expect(() => plantedRed(planted, 'planted failure', 'T005 PLANTED'), 'T005 RED planted').not.toThrow()
}, 60_000)

test.each([
  ['an import failure carrying the witness', 'mutation/fixtures/broken/vitest.config.ts'],
  ['a hook error', 'mutation/fixtures/hook/vitest.config.ts'],
  ['an unhandled rejection', 'mutation/fixtures/unhandled/vitest.config.ts'],
  ['no collected test', 'mutation/fixtures/empty/vitest.config.ts'],
  ['a missing config', 'mutation/planted/no-such.config.ts'],
])('%s is not accepted as red proof', (_label, config) => {
  expect(() => plantedRed(config, 'planted failure', 'T005 PLANTED'), 'T005 RED refused').toThrow(/not shown/)
}, 60_000)

test('a different failing test name is not accepted as red proof', () => {
  expect(() => plantedRed(planted, 'some other test', 'T005 PLANTED'), 'T005 RED name').toThrow(/not shown/)
}, 60_000)
