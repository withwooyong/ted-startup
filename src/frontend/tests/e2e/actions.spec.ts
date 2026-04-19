import { test, expect } from '@playwright/test';
import { PortfolioPage } from './pages/PortfolioPage';

// 격리 전략: dedicated 테스트 계좌 생성 없이 단순 부수효과 허용.
// C1 는 portfolio_snapshot 에 +1 행을 남기지만 멱등하고 누적 무해.
// C2 는 KIS 어댑터가 "mock" 이름과 달리 실제 외부 토큰 API 를 호출하며 1분당 1회
//     rate limit 에 걸린다. E2E 목적은 프론트 UX 검증이므로 sync 엔드포인트를
//     intercept 하여 deterministic 응답으로 대체.

test.describe('C. 포트폴리오 액션 (쓰기 경로)', () => {
  test('C1: 스냅샷 생성 → 배너 "스냅샷 저장 완료: 평가금액 …"', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await portfolio.goto();
    await expect(portfolio.accountTabs).toBeVisible();
    await expect(portfolio.holdingsTable).toBeVisible();

    // 클릭 → 진행 중 표시 → 완료 배너
    await portfolio.snapshotButton.click();

    // role=status 배너에 성공 메시지
    const banner = page.getByRole('status');
    await expect(banner).toBeVisible({ timeout: 10_000 });
    await expect(banner).toContainText(/스냅샷 저장 완료/);
    await expect(banner).toContainText(/평가금액/);
  });

  test('C2: KIS 모의 동기화 (e2e-kis 계좌) → 배너 "KIS 동기화 완료: 신규 X · 갱신 X · 그대로 X"', async ({ page }) => {
    // KIS rate limit 회피 — sync 엔드포인트를 stub 해 프론트 UX 만 검증.
    await page.route('**/api/admin/portfolio/accounts/*/sync', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          account_id: 2,
          connection_type: 'kis_rest_mock',
          fetched_count: 0,
          created_count: 3,
          updated_count: 1,
          unchanged_count: 2,
          stock_created_count: 0,
        }),
      }),
    );

    const portfolio = new PortfolioPage(page);
    await portfolio.goto();
    await expect(portfolio.accountTabs).toBeVisible();
    await portfolio.selectAccount('e2e-kis');
    await expect(portfolio.kisSyncButton).toBeVisible();

    await portfolio.kisSyncButton.click();

    await expect(page.getByText(/KIS 동기화 완료/)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('신규 3 · 갱신 1 · 그대로 2')).toBeVisible();
  });
});
