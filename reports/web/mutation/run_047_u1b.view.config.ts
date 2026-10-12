// Spec 047 T008/T009: the single view test the U1b mutants run against (jsdom, React).
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', include: ['src/components/views/BacktestTearsheetView.test.tsx'] },
})
