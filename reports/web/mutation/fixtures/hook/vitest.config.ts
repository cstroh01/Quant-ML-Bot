import { defineConfig } from 'vitest/config'
export default defineConfig({ test: { include: ['mutation/fixtures/hook/*.test.ts'] } })
