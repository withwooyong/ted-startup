import { test, expect } from '@playwright/test';

test.describe('F. 주식 상세', () => {
  test('F1: /stocks/005930 접근 — 종목명·코드·현재가 렌더', async ({ page }) => {
    await page.goto('/stocks/005930');

    // 로딩 스켈레톤 끝난 뒤 실제 콘텐츠
    await expect(page.getByText('삼성전자').first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('005930').first()).toBeVisible();
    await expect(page.getByText('현재가')).toBeVisible();
    await expect(page.getByText('전일비')).toBeVisible();
    await expect(page.getByText('거래량')).toBeVisible();
  });

  test('F2: 기간 1M 버튼 클릭 → aria-pressed 전환', async ({ page }) => {
    await page.goto('/stocks/005930');
    await expect(page.getByText('삼성전자').first()).toBeVisible({ timeout: 10_000 });

    const m1 = page.getByRole('button', { name: '1M' });
    await m1.click();
    await expect(m1).toHaveAttribute('aria-pressed', 'true');

    // 기본값 3M 은 눌려있지 않게 됨
    await expect(page.getByRole('button', { name: '3M' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  test('F3: 대시보드 복귀 링크', async ({ page }) => {
    await page.goto('/stocks/005930');
    await expect(page.getByText('삼성전자').first()).toBeVisible({ timeout: 10_000 });

    await page.getByRole('button', { name: '대시보드로 돌아가기' }).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test('F4: 존재하지 않는 종목 /stocks/999999 → 에러 영역', async ({ page }) => {
    await page.goto('/stocks/999999');
    // role="alert" 는 Next route announcer 와 충돌 → 페이지 고유 엘리먼트(버튼)로 단언
    await expect(page.getByRole('button', { name: /대시보드로 이동/ })).toBeVisible({
      timeout: 10_000,
    });
  });
});
