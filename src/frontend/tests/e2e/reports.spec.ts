import { test, expect } from '@playwright/test';

test.describe('G. AI 리포트', () => {
  test('G1: /reports/005930 접근 — breadcrumb 렌더', async ({ page }) => {
    await page.goto('/reports/005930');

    // NavHeader 의 "포트폴리오" 링크와 구분하기 위해 main 영역으로 스코프 제한
    const main = page.getByRole('main');
    await expect(main.getByRole('link', { name: '포트폴리오' })).toBeVisible({
      timeout: 15_000,
    });
    await expect(main.getByRole('link', { name: '종목' })).toBeVisible();
    await expect(main.getByText('AI 리포트')).toBeVisible();
  });

  test('G2: breadcrumb "포트폴리오" 링크 → /portfolio', async ({ page }) => {
    await page.goto('/reports/005930');
    const breadcrumbLink = page
      .getByRole('main')
      .getByRole('link', { name: '포트폴리오' });
    await expect(breadcrumbLink).toBeVisible({ timeout: 15_000 });

    await breadcrumbLink.click();
    await expect(page).toHaveURL(/\/portfolio$/);
  });
});
