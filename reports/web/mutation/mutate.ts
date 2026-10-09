// Spec 047 T005: TypeScript mutation helper for web view tests (Rule 12).
//
// runMutant edits exactly one site of one source file, runs one vitest config, and
// restores the file byte-for-byte (verified by SHA-256) whatever happens. Outcomes:
//   killed       - at least one failure whose message carries the witness
//   survived     - every test passed against the mutant
//   other        - failures, none carrying the witness (never counted as a kill)
// A replacement that would hit zero or two-plus sites is refused before any edit.
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export type Outcome = 'killed' | 'survived' | 'other'

export interface Mutant {
  file: string
  find: string
  replace: string
  config: string
  witness: string
}

const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')

function failures(config: string): { ran: boolean; messages: string[] } {
  const dir = mkdtempSync(join(tmpdir(), 'mut-'))
  const out = join(dir, 'report.json')
  try {
    spawnSync(process.execPath, ['node_modules/vitest/vitest.mjs', 'run', '--config', config,
      '--reporter=json', `--outputFile=${out}`], { encoding: 'utf-8' })
    const report = JSON.parse(readFileSync(out, 'utf-8'))
    const messages: string[] = []
    for (const file of report.testResults ?? []) {
      for (const t of file.assertionResults ?? []) {
        if (t.status === 'failed') messages.push((t.failureMessages ?? []).join('\n'))
      }
      if (file.status === 'failed' && (file.assertionResults ?? []).length === 0) messages.push(file.message ?? '')
    }
    return { ran: (report.numTotalTests ?? 0) > 0, messages }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
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
    const { ran, messages } = failures(m.config)
    if (!ran) throw new Error('refused: no test collected')
    outcome = messages.length === 0 ? 'survived'
      : messages.some((msg) => msg.includes(m.witness)) ? 'killed' : 'other'
  } finally {
    writeFileSync(m.file, original)
  }
  if (sha(readFileSync(m.file)) !== digest) throw new Error('source not restored byte-for-byte')
  return outcome
}

export function control(config: string): void {
  const { ran, messages } = failures(config)
  if (!ran || messages.length > 0) throw new Error('unmutated control is not green')
}
