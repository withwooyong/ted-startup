import { test, expect } from '@playwright/test';

test.describe('H. 백테스트', () => {
  test('H1: /backtest → h1 "Backtest Results"', async ({ page }) => {
    await page.goto('/backtest');

    await expect(
      page.getByRole('heading', { level: 1, name: 'Backtest Results' }),
    ).toBeVisible();
  });

  test('H2: backtest_result 0건 → empty state', async ({ page }) => {
    // 현 DB 기준 backtest_result 는 0 건. 미래에 데이터가 생기면 이 테스트를
    // 업데이트해야 함.
    await page.goto('/backtest');

    await expect(page.getByText('백테스팅을 아직 실행하지 않았어요')).toBeVisible({
      timeout: 10_000,
    });
  });
});
