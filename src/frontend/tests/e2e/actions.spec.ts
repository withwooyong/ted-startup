import { test, expect } from '@playwright/test';
import { PortfolioPage } from './pages/PortfolioPage';

// 격리 전략: dedicated 테스트 계좌 생성 없이 단순 부수효과 허용.
// C1 는 portfolio_snapshot 에 +1 행을 남기지만 멱등하고 누적 무해.
// C2 는 mock 어댑터라 실제 외부 호출 없이 동일 결과 반환 (멱등).

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
    const portfolio = new PortfolioPage(page);
    await portfolio.goto();
    await expect(portfolio.accountTabs).toBeVisible();
    await portfolio.selectAccount('e2e-kis');
    await expect(portfolio.kisSyncButton).toBeVisible();

    await portfolio.kisSyncButton.click();

    const banner = page.getByRole('status');
    await expect(banner).toBeVisible({ timeout: 15_000 });
    await expect(banner).toContainText(/KIS 동기화 완료/);
    await expect(banner).toContainText(/신규 \d+ · 갱신 \d+ · 그대로 \d+/);
  });
});
