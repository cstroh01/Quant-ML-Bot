// Spec 047 T015 driver config. Never part of the default suite: its mutants edit
// BacktestTearsheetView.tsx in place, which would race the view test in another worker.
import { defineConfig } from 'vitest/config'
export default defineConfig({ test: { include: ['mutation/run_047_u3.mutants.ts'], fileParallelism: false } })
