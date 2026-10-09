// Spec 047 T005 control: the runtime runner renders real React into jsdom.
// EXAMPLE — NOT A RESULT. Synthetic markup only.
import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

function Probe({ value }: { value: number | null }) {
  return <span data-testid="probe">{value === null ? 'N/A' : value.toFixed(2)}</span>
}

test('renders null distinctly from zero', () => {
  render(<Probe value={null} />)
  expect(screen.getByTestId('probe').textContent, 'T005 RENDER null').toBe('N/A')
})

test('renders a finite value', () => {
  render(<Probe value={0} />)
  expect(screen.getAllByTestId('probe').at(-1)?.textContent, 'T005 RENDER zero').toBe('0.00')
})
