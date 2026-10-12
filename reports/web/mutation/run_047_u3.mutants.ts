// Spec 047 T015 Rule 12: U3 null-drawdown mutants. EXAMPLE — NOT A RESULT.
// Run: npx vitest run --config mutation/run_047_u3.config.ts (from reports/web).
// Each mutant edits one site of the view, runs only the view test (the U1b view config), and is
// restored byte-for-byte (mutate.ts). A kill is a named assertion failing with the witness.
import { expect, test } from 'vitest'
import { control, runMutant } from './mutate'

const file = 'src/components/views/BacktestTearsheetView.tsx'
const config = 'mutation/run_047_u1b.view.config.ts'

test('control: the unmutated view passes its test', () => {
  expect(() => control(config), '047 U3 control').not.toThrow()
}, 120_000)

test.each([
  // M6 (tasks.md T014): the formatter's fallback reverted to the fabricated '0.00%'.
  ['M6 fallback 0.00%', "return value === null ? 'N/A'", "return value === null ? '0.00%'", '047 U3 null'],
  // M6b: the card bypasses the formatter with the old expression.
  ['M6b card bypasses formatter', '{formatPercentOrNA(tearsheet.max_drawdown)}',
    "{tearsheet.max_drawdown !== null ? `${tearsheet.max_drawdown.toFixed(2)}%` : '0.00%'}", '047 U3 card null'],
  // M6c: the baseline table's em dash replaced by the card formatter (FR-007 keeps '—' there).
  ['M6c baseline dash replaced', "{row.max_drawdown !== null ? `${row.max_drawdown.toFixed(2)}%` : '—'}",
    '{formatPercentOrNA(row.max_drawdown)}', '047 U3 baseline dash'],
])('%s is killed', (name, find, replace, witness) => {
  expect(runMutant({ file, config, find, replace, witness }), `047 U3 ${name}`).toBe('killed')
}, 120_000)
