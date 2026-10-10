// Spec 047 T005: TypeScript mutation helper for web view tests (Rule 12).
//
// runMutant edits exactly one site of one source file, runs one vitest config, and
// restores the file byte-for-byte (verified by SHA-256) whatever happens. Outcomes:
//   killed       - a named assertion failed with the witness, and the run is otherwise clean
//   survived     - every collected test passed, exit 0, no runner error
//   other        - assertion failures, none carrying the witness (never counted as a kill)
//   error        - a runner, import, collection, unhandled or spawn error, an unreadable
//                  report, or an exit status inconsistent with the report (never a kill)
// A replacement that would hit zero or two-plus sites is refused before any edit.
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export type Outcome = 'killed' | 'survived' | 'other' | 'error'

export interface Mutant {
  file: string
  find: string
  replace: string
  config: string
  witness: string
}

/** One vitest process: exit status, spawn error, parsed JSON report (null if absent), console text. */
export interface Run {
  status: number | null
  spawnError?: string
  report: unknown
  output: string
}

export interface Summary {
  status: number | null
  collected: number
  failures: { name: string; message: string }[]
  runnerErrors: string[]
}

const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')

/** Runs one config with the JSON reporter. Never throws; every problem lands in the Run. */
export function runConfig(config: string): Run {
  const dir = mkdtempSync(join(tmpdir(), 'mut-'))
  const out = join(dir, 'report.json')
  try {
    const child = spawnSync(process.execPath, ['node_modules/vitest/vitest.mjs', 'run', '--config', config,
      '--reporter=json', `--outputFile=${out}`], { encoding: 'utf-8', maxBuffer: 64 * 1024 * 1024 })
    let report: unknown = null
    try { report = JSON.parse(readFileSync(out, 'utf-8')) } catch { report = null }
    return { status: child.status, spawnError: child.error?.message, report,
      output: `${child.stdout ?? ''}\n${child.stderr ?? ''}` }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

interface FileResult { name?: string; status?: string; message?: string; assertionResults?: AssertionResult[] }
interface AssertionResult { status?: string; fullName?: string; title?: string; failureMessages?: string[] }

/**
 * Separates named assertion failures from everything else. Guarantees: a suite-level
 * message, a failed file with no failed assertion, an unhandled error, a missing report,
 * a spawn error, zero collected tests, or an exit status that disagrees with the
 * assertion results is a runner error, and never appears in `failures`.
 */
export function summarize(run: Run): Summary {
  const runnerErrors: string[] = []
  const failures: { name: string; message: string }[] = []
  let collected = 0
  if (run.spawnError) runnerErrors.push(`spawn error: ${run.spawnError}`)
  if (run.status === null) runnerErrors.push('runner exited without a status')
  const report = run.report as { testResults?: FileResult[] } | null
  if (!report || !Array.isArray(report.testResults)) {
    runnerErrors.push('JSON report missing or unparseable')
  } else {
    for (const file of report.testResults) {
      const asserts = file.assertionResults ?? []
      collected += asserts.length
      const failed = asserts.filter((t) => t.status === 'failed')
      for (const t of failed) {
        failures.push({ name: t.fullName ?? t.title ?? '', message: (t.failureMessages ?? []).join('\n') })
      }
      if (file.message) runnerErrors.push(`suite error in ${file.name ?? '?'}: ${file.message}`)
      else if (file.status === 'failed' && failed.length === 0) runnerErrors.push(`suite failed without a failed assertion: ${file.name ?? '?'}`)
    }
  }
  if (/Unhandled (Errors?|Rejections?)/.test(run.output)) runnerErrors.push('unhandled error reported by the runner')
  if (collected === 0) runnerErrors.push('no test collected')
  if (run.status === 0 && failures.length > 0) runnerErrors.push('exit 0 despite failed assertions')
  if (run.status !== null && run.status !== 0 && failures.length === 0 && runnerErrors.length === 0) {
    runnerErrors.push(`exit ${run.status} with no failed assertion`)
  }
  return { status: run.status, collected, failures, runnerErrors }
}

export function classify(s: Summary, witness: string): Outcome {
  if (s.runnerErrors.length > 0) return 'error'
  if (s.failures.length === 0) return 'survived'
  return s.failures.some((f) => f.message.includes(witness)) ? 'killed' : 'other'
}

/** Throws unless the run is a clean green control: exit 0, tests collected, no failure, no runner error. */
export function checkControl(s: Summary): void {
  if (s.status !== 0 || s.collected === 0 || s.failures.length > 0 || s.runnerErrors.length > 0) {
    throw new Error(`unmutated control is not green: ${JSON.stringify(s)}`)
  }
}

/** Throws unless exactly the named planted test failed on its witness, with no runner error. */
export function checkPlanted(s: Summary, name: string, witness: string): void {
  const ok = s.status !== 0 && s.status !== null && s.runnerErrors.length === 0 && s.failures.length === 1
    && s.failures[0].name === name && s.failures[0].message.includes(witness)
  if (!ok) throw new Error(`planted red proof not shown: ${JSON.stringify(s)}`)
}

export function runMutant(m: Mutant): Outcome {
  const original = readFileSync(m.file)
  const text = original.toString('utf-8')
  const sites = text.split(m.find).length - 1
  if (sites !== 1) throw new Error(`refused: replacement must hit exactly one site, found ${sites}`)
  const digest = sha(original)
  let outcome: Outcome
  try {
    writeFileSync(m.file, text.replace(m.find, m.replace), 'utf-8')
    outcome = classify(summarize(runConfig(m.config)), m.witness)
  } finally {
    writeFileSync(m.file, original)
  }
  if (sha(readFileSync(m.file)) !== digest) throw new Error('source not restored byte-for-byte')
  return outcome
}

export function control(config: string): void {
  checkControl(summarize(runConfig(config)))
}

export function plantedRed(config: string, name: string, witness: string): void {
  checkPlanted(summarize(runConfig(config)), name, witness)
}
