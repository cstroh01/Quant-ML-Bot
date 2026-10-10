// Spec 047 T005 Rule 12 for the helper itself. EXAMPLE — NOT A RESULT.
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { checkControl, classify, control, runMutant, summarize, type Run } from './mutate'

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

// Runner errors are never kills and never green controls (Codex B1 #141 P1).
test('an import-time error carrying the witness is an error, not a kill', () => {
  const before = digest()
  const mutant = { ...base, find: 'export function untested', replace: "throw new Error('SAMPLE ADD at import')\nexport function untested" }
  expect(runMutant(mutant), 'T005 HELPER import error').toBe('error')
  expect(digest(), 'T005 HELPER import restore').toBe(before)
}, 60_000)

test('a passing test beside a failed import suite carrying the witness is an error, not a kill', () => {
  const broken = { ...base, config: 'mutation/fixtures/broken/vitest.config.ts' }
  expect(runMutant({ ...broken, find: "return 'untested'", replace: "return 'changed'" }), 'T005 HELPER broken kill').toBe('error')
}, 60_000)

test.each(['broken', 'hook', 'unhandled', 'empty'])('control refuses the %s fixture', (name) => {
  expect(() => control(`mutation/fixtures/${name}/vitest.config.ts`), `T005 HELPER control ${name}`).toThrow(/not green/)
}, 60_000)

test('control refuses a missing config', () => {
  expect(() => control('mutation/fixtures/no-such.config.ts'), 'T005 HELPER control missing').toThrow(/not green/)
}, 60_000)

// Controlled reports: the exit-status and report rules, independent of vitest's own output.
const passing = { name: 'a.test.ts', status: 'passed', message: '', assertionResults: [{ status: 'passed', fullName: 'ok' }] }
const run = (status: number | null, testResults: unknown[] | null, extra: Partial<Run> = {}): Run =>
  ({ status, report: testResults === null ? null : { testResults }, output: '', ...extra })

test.each([
  ['nonzero exit, no failed assertion', run(1, [passing])],
  ['exit 0 with a failed assertion', run(0, [{ ...passing, status: 'failed', assertionResults: [{ status: 'failed', fullName: 'f', failureMessages: ['SAMPLE ADD'] }] }])],
  ['failed suite with zero assertions beside a pass', run(1, [passing, { name: 'b.test.ts', status: 'failed', message: 'SAMPLE ADD', assertionResults: [] }])],
  ['suite message beside a witnessed assertion failure', run(1, [{ name: 'c.test.ts', status: 'failed', message: 'SAMPLE ADD hook', assertionResults: [{ status: 'failed', fullName: 'f', failureMessages: ['SAMPLE ADD'] }] }])],
  ['unhandled error text', run(1, [{ ...passing, status: 'failed', assertionResults: [{ status: 'failed', fullName: 'f', failureMessages: ['SAMPLE ADD'] }] }], { output: 'Unhandled Rejection' })],
  ['spawn error', run(null, null, { spawnError: 'ENOENT' })],
  ['missing report', run(1, null)],
  ['no test collected', run(0, [])],
])('%s is an error and never a green control', (_label, r) => {
  const s = summarize(r)
  expect(classify(s, 'SAMPLE ADD'), 'T005 HELPER report error').toBe('error')
  expect(() => checkControl(s), 'T005 HELPER report control').toThrow(/not green/)
})

test('checkControl alone refuses a nonzero exit, independent of summarize', () => {
  const s = { status: 1, collected: 1, failures: [], runnerErrors: [] }
  expect(() => checkControl(s), 'T005 HELPER control status').toThrow(/not green/)
})

test('a clean witnessed assertion failure is the kill control', () => {
  const s = summarize(run(1, [passing, { name: 'd.test.ts', status: 'failed', message: '', assertionResults: [{ status: 'failed', fullName: 'f', failureMessages: ['SAMPLE ADD: expected 5'] }] }]))
  expect(classify(s, 'SAMPLE ADD'), 'T005 HELPER report kill').toBe('killed')
})
