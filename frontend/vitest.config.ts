import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config.ts'

export default mergeConfig(viteConfig, defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    clearMocks: true,
    restoreMocks: true,
    maxWorkers: 2,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/app/App.tsx', 'src/features/search/*.{ts,tsx}', 'src/lib/api/**/*.ts'],
      exclude: ['**/*.test.{ts,tsx}', '**/types.ts'],
      thresholds: { perFile: true, statements: 95, branches: 95, functions: 95, lines: 95 },
    },
  },
}))
