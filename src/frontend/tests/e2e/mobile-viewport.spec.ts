import { test, expect } from '@playwright/test';

test.describe('Phase A: 모바일 뷰포트 기반', () => {
  test('layout.tsx 의 viewport export 가 <meta name="viewport"> 로 렌더', async ({ page }) => {
    await page.goto('/');

    const viewport = page.locator('meta[name="viewport"]');
    await expect(viewport).toHaveAttribute(
      'content',
      /width=device-width.*initial-scale=1.*maximum-scale=5/,
    );
  });

  test('홈(/) 이 모바일 프로필에서 가로 스크롤 없이 렌더', async ({ page }) => {
    await page.goto('/');

    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      return doc.scrollWidth - doc.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
