import { defineConfig } from 'vitest/config'
// Collects nothing: the include matches no file.
export default defineConfig({ test: { include: ['mutation/fixtures/empty/*.test.ts'] } })
