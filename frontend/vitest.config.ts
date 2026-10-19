import { defineConfig, mergeConfig } from 'vite'
import viteConfig from './vite.config'

// Vitest configuration. Reuses the Vite resolve aliases (so `@/` works in tests)
// and adds a jsdom environment plus a shared setup file.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      restoreMocks: true,
    },
  }),
)
