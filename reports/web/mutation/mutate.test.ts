// Spec 047 T005 Rule 12 for the helper itself. EXAMPLE — NOT A RESULT.
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { control, runMutant } from './mutate'

const file = 'mutation/fixtures/sample.ts'
const config = 'mutation/fixtures/vitest.config.ts'
const digest = () => createHash('sha256').update(readFileSync(file)).digest('hex')
const base = { file, config, witness: 'SAMPLE ADD' }

test('unmutated fixture is the green control', () => {
  expect(() => control(config), 'T005 HELPER control').not.toThrow()
}, 60_000)

test('a detected mutant is killed and the source is restored', () => {
  const before = digest()
  expect(runMutant({ ...base, find: 'return a + b', replace: 'return a - b' }), 'T005 HELPER killed').toBe('killed')
  expect(digest(), 'T005 HELPER restore').toBe(before)
}, 60_000)

test('an undetected mutant survives', () => {
  expect(runMutant({ ...base, find: "return 'untested'", replace: "return 'changed'" }), 'T005 HELPER survived').toBe('survived')
}, 60_000)

test('a failure without the witness is not counted as a kill', () => {
  expect(runMutant({ ...base, find: 'return a + b', replace: "throw new Error('boom')" }), 'T005 HELPER other').toBe('other')
}, 60_000)

test('replacements hitting zero or two sites are refused before any edit', () => {
  const before = digest()
  expect(() => runMutant({ ...base, find: 'no such text', replace: 'x' }), 'T005 HELPER zero').toThrow(/exactly one site/)
  expect(() => runMutant({ ...base, find: 'return', replace: 'return' }), 'T005 HELPER two').toThrow(/exactly one site/)
  expect(digest(), 'T005 HELPER untouched').toBe(before)
})
