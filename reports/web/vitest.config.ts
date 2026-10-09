import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Spec 047 D-1 (a): runtime view tests. Mutation fixtures and the planted red case
// run only through their own configs, never in the default suite.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}', 'mutation/*.test.ts'],
    exclude: ['mutation/fixtures/**', 'mutation/planted/**', 'node_modules/**'],
  },
})
