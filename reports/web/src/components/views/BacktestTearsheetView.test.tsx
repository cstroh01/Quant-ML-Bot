// Spec 047 T008 (FR-002, FR-008): the friction card shows the response's charged totals and does no
// friction arithmetic. EXAMPLE — NOT A RESULT. Synthetic fixture; charts are stubbed (no canvas in jsdom).
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { tearsheet047 } from '../../test/fixtures/tearsheet047'
import { BacktestTearsheetView } from './BacktestTearsheetView'

vi.mock('../charts/CandlestickChart', () => ({ CandlestickChart: () => null }))
vi.mock('../charts/DrawdownChart', () => ({ DrawdownChart: () => null }))
vi.mock('../charts/EquityCurveChart', () => ({ EquityCurveChart: () => null }))

afterEach(cleanup)

const params = { shortWindow: 10, longWindow: 30, commission: 1, slippageBps: 5 }
const view = (tearsheet = tearsheet047) => render(
  <BacktestTearsheetView tearsheet={tearsheet} ohlcv={[]} loading={false} colorblindMode={false}
    currentParams={params} onApplyParams={() => {}} />)
const text = (id: string) => screen.getByTestId(id).textContent ?? ''

test('commission and slippage are the response totals, as given', () => {
  view()
  // The perturbed fields are commission_total and slippage_total; trade count and commission_per_trade
  // are chosen so the old formula (2 * $1.00 * 2 trades = $4.00) cannot coincide with $3.00.
  expect(text('friction-commission'), '047 U1B commission').toContain('$3.00')
  expect(text('friction-slippage'), '047 U1B slippage').toContain('$0.47')
})

test('the card does no friction arithmetic: no sum and no per-trade product', () => {
  view()
  const card = text('friction-card')
  expect(card, '047 U1B no sum').not.toContain('3.47')
  expect(card, '047 U1B no product').not.toContain('4.00')
})

test('the figures follow the response, not the trade count', () => {
  view({ ...tearsheet047, commission_total: 7.25, slippage_total: 0 })
  expect(text('friction-commission'), '047 U1B commission').toContain('$7.25')
  expect(text('friction-slippage'), '047 U1B slippage').toContain('$0.00')
})

test('the labels name commission and flat-bps modeled slippage', () => {
  view()
  const card = text('friction-card').toLowerCase()
  for (const word of ['commission', 'slippage', 'flat bps', 'modeled']) {
    expect(card, `047 U1B label ${word}`).toContain(word)
  }
})

test('FR-008: 038-owned text in the card and header row is unchanged', () => {
  view()
  const card = text('friction-card')
  expect(card, '047 U1B FR-008 header').toContain('FRICTION MODEL')
  expect(card, '047 U1B FR-008 params').toContain('$1.00 / 5.0 bps')
  expect(card, '047 U1B FR-008 badge').toContain('✓ 1e-9')
  expect(screen.getByText('Rf = 3.78% (3m T-Bill)'), '047 U1B FR-008 Rf').toBeTruthy()
})
