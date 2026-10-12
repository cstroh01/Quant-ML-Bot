// Spec 047 T009 Rule 12: U1b view mutants. EXAMPLE — NOT A RESULT.
// Run: npx vitest run --config mutation/run_047_u1b.config.ts (from reports/web).
// Each mutant edits one site of the view, runs only the view test, and is restored byte-for-byte
// (mutate.ts). A kill is a named assertion failing with the witness; runner errors never count.
import { expect, test } from 'vitest'
import { control, runMutant } from './mutate'

const file = 'src/components/views/BacktestTearsheetView.tsx'
const config = 'mutation/run_047_u1b.view.config.ts'
const COMMISSION = '${tearsheet.commission_total.toFixed(2)}'
const SLIPPAGE = '${tearsheet.slippage_total.toFixed(2)}'

test('control: the unmutated view passes its test', () => {
  expect(() => control(config), '047 U1B control').not.toThrow()
}, 120_000)

test.each([
  // V1 (tasks.md T008): the commission figure reverted to the old per-trade product.
  ['V1 per-trade product', COMMISSION, '${(tearsheet.trade_log.length * (2 * tearsheet.commission_per_trade)).toFixed(2)}', '047 U1B commission'],
  // V1b: the view sums friction into the commission line (FR-002 forbids view arithmetic).
  ['V1b view-side sum', COMMISSION, '${(tearsheet.commission_total + tearsheet.slippage_total).toFixed(2)}', '047 U1B commission'],
  // V2: slippage shown from the configured bps instead of the charged dollars.
  ['V2 slippage from bps', SLIPPAGE, '${tearsheet.slippage_bps.toFixed(2)}', '047 U1B slippage'],
  // V3: the label stops saying the slippage is modeled.
  ['V3 label drops modeled', 'Slippage (flat bps, modeled):', 'Slippage (flat bps):', '047 U1B label modeled'],
])('%s is killed', (_name, find, replace, witness) => {
  expect(runMutant({ file, config, find, replace, witness }), `047 U1B ${_name}`).toBe('killed')
}, 120_000)
