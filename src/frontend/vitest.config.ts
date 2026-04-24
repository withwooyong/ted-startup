import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', '.next', 'tests/**', 'playwright-report/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      include: ['src/lib/indicators/**/*.ts'],
      exclude: ['**/*.test.ts', '**/*.test.tsx', '**/index.ts'],
      thresholds: {
        'src/lib/indicators/**/*.ts': { lines: 90, branches: 90, functions: 90, statements: 90 },
        // NOTE v1.2 Cp 2 에서 `src/lib/hooks/useIndicatorPreferences.ts` 100% 임계 + hooks include 추가 예정
      },
    },
  },
});
