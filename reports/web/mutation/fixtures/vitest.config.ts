import { defineConfig } from 'vitest/config'
export default defineConfig({ test: { include: ['mutation/fixtures/*.test.ts'] } })
