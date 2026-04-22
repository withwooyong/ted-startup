import { test, expect } from '@playwright/test';
import { PortfolioPage } from './pages/PortfolioPage';

test.describe('B. 포트폴리오 리스트', () => {
  // 본 스펙은 데스크톱 테이블(`<table>`, hidden sm:block)을 전제로 작성됐다.
  // 모바일 프로필(mobile-safari/mobile-chrome)에선 테이블이 숨겨지고 카드 리스트가
  // 대체 렌더되므로 `holdingsTable.toBeVisible()` 이 실패한다. 모바일 경로는
  // `mobile.spec.ts` 가 `data-testid="holding-row"` 로 별도 검증한다.
  test.beforeEach(async ({ page }, testInfo) => {
    test.skip(
      testInfo.project.name !== 'chromium',
      '데스크톱 테이블 전제 — 모바일 경로는 mobile.spec.ts 에서 검증',
    );
    const portfolio = new PortfolioPage(page);
    await portfolio.goto();
    // 첫 API 응답 대기 (listAccounts → listHoldings → getPerformance)
    await expect(portfolio.accountTabs).toBeVisible();
  });

  test('B1: 진입 시 첫 계좌(e2e-manual) 기본 선택', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await expect(portfolio.accountTab('e2e-manual')).toHaveAttribute('aria-selected', 'true');
  });

  test('B2: Metric 4개 렌더 — 보유 종목 수=1, 매입 원가=720,000', async ({ page }) => {
    const portfolio = new PortfolioPage(page);

    // 보유 종목 로드 대기
    await expect(portfolio.holdingsTable).toBeVisible();

    const labels = ['보유 종목 수', '매입 원가 합계', '누적 수익률 (3M)', 'MDD (3M)'];
    for (const label of labels) {
      await expect(portfolio.metricsSection.getByText(label)).toBeVisible();
    }
    // 보유 종목 수 값 = 1
    await expect(portfolio.metricsSection.getByText(/^1$/).first()).toBeVisible();
    // 매입 원가 = 720,000
    await expect(portfolio.metricsSection.getByText('720,000')).toBeVisible();
  });

  test('B3: 보유 종목 테이블 — 삼성전자 1행', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await expect(portfolio.holdingsTable).toBeVisible();

    const row = portfolio.holdingRow('005930');
    await expect(row).toBeVisible();
    await expect(row).toContainText('삼성전자');
    await expect(row).toContainText('005930');
    await expect(row).toContainText('10');
    // 평단·매입원가는 모두 '72,000' 부분 문자열 포함 (소수점 0일 때 생략됨)
    await expect(row).toContainText('72,000');
    await expect(row).toContainText('720,000');
  });

  test('B4: 종목명 링크 클릭 → /stocks/005930', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await expect(portfolio.holdingsTable).toBeVisible();

    const row = portfolio.holdingRow('005930');
    await row.getByRole('link', { name: '삼성전자' }).click();

    await expect(page).toHaveURL(/\/stocks\/005930$/);
  });

  test('B5: "AI 리포트 →" 버튼 → /reports/005930', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await expect(portfolio.holdingsTable).toBeVisible();

    const row = portfolio.holdingRow('005930');
    await row.getByRole('link', { name: /AI 리포트/ }).click();

    await expect(page).toHaveURL(/\/reports\/005930$/);
  });

  test('B6: 계좌 탭 전환(e2e-kis) → 빈 상태', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await portfolio.selectAccount('e2e-kis');

    await expect(portfolio.accountTab('e2e-kis')).toHaveAttribute('aria-selected', 'true');
    await expect(portfolio.emptyHoldings).toBeVisible();
  });

  test('B7: 조건부 UI — KIS 모의 동기화 버튼', async ({ page }) => {
    const portfolio = new PortfolioPage(page);

    // manual 계좌에선 비노출
    await expect(portfolio.kisSyncButton).toHaveCount(0);

    // kis 계좌로 전환 시 노출
    await portfolio.selectAccount('e2e-kis');
    await expect(portfolio.kisSyncButton).toBeVisible();
  });
});
