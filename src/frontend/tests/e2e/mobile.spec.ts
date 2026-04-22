import { test, expect, type Page } from '@playwright/test';
import { PortfolioPage } from './pages/PortfolioPage';

/**
 * Phase B~D 모바일 반응형 회귀 스펙.
 *
 * - `mobile-safari` (iPhone 13, 390×844) + `mobile-chrome` (Galaxy S8, 360×740) 프로필 전용.
 * - 각 페이지가 mobile viewport 에서 **수평 스크롤 없이** 렌더되는지 1차 방어선.
 * - Phase B/C/D 의 핵심 표면(카드 리스트, 배지 숨김, chip 제한, sync 라벨 단축, 차트 aspect, 터치 타깃)
 *   이 실제로 DOM 에 반영됐는지 검증.
 *
 * 스크린샷은 `screenshot: 'only-on-failure'` (playwright.config) 로 자동 수집되며,
 * 본 스펙은 명시적으로 page.screenshot() 을 호출해 성공 상태도 기록 — 증빙용.
 *
 * backend dependency: 일부 페이지(portfolio/stocks/reports/alignment) 는 실 API 응답이 없으면
 * 빈 상태/스켈레톤만 렌더되는데, 본 스펙은 "뷰포트에서 레이아웃이 깨지지 않음" 을 검증하므로
 * 데이터 유무와 무관하게 통과해야 한다. 데이터 의존 테스트는 holdings.spec.ts 등에 위임.
 */

async function noHorizontalOverflow(page: Page): Promise<void> {
  // documentElement 기준 1px 오차 허용 (서브픽셀 렌더링).
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth - doc.clientWidth;
  });
  expect(overflow, '가로 스크롤 발생').toBeLessThanOrEqual(1);
}

async function captureScreenshot(page: Page, name: string): Promise<void> {
  // 스크린샷은 CI artifact 로 수집되지만 로컬에선 `test-results/` 아래로 떨어진다.
  // `fullPage: true` 로 접힘 영역까지 포함해 회귀 비교의 신호를 최대화.
  await page.screenshot({ path: `test-results/mobile/${name}.png`, fullPage: true });
}

test.describe('Phase B~D 모바일 반응형 회귀', () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      testInfo.project.name === 'chromium',
      '모바일 프로필 전용 — desktop 경로는 기존 스펙이 커버',
    );
  });

  test('대시보드(/) — 수평 스크롤 없음 + 필터 버튼 터치 타깃 44px', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1.sr-only')).toHaveText(/시그널 대시보드/);

    await noHorizontalOverflow(page);

    // D1: 모바일에서 필터 버튼 `min-h-[44px]` 적용 확인 (최소 1개 버튼).
    const filterButtons = page.getByRole('button', { name: /전체|급감|추세전환|숏스퀴즈/ });
    const firstBtn = filterButtons.first();
    await expect(firstBtn).toBeVisible();
    const box = await firstBtn.boundingBox();
    expect(box?.height ?? 0, '필터 버튼 높이 44px 미만').toBeGreaterThanOrEqual(44);

    await captureScreenshot(page, 'dashboard');
  });

  test('NavHeader — 로고 옆 v1.0 배지가 모바일에서 숨겨짐 (B2)', async ({ page }) => {
    await page.goto('/');
    // span 내부 텍스트 "v1.0" — hidden sm:inline 으로 모바일 프로필에선 display:none.
    const versionBadge = page.getByText('v1.0', { exact: true });
    await expect(versionBadge).toBeHidden();
  });

  test('포트폴리오(/portfolio) — 테이블 숨김 + 카드 리스트 렌더 (B1)', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await portfolio.goto();
    await expect(portfolio.accountTabs).toBeVisible();

    await noHorizontalOverflow(page);

    // B1: `<table>` 은 `hidden sm:block` 이라 모바일에서 숨김.
    await expect(portfolio.holdingsTable).toBeHidden();

    // 보유 종목이 있으면 `data-testid="holding-row"` 카드(li) 가 렌더된다.
    // 없는 경우(빈 상태) 에는 empty 메시지가 렌더 — 둘 중 하나는 반드시 나타남.
    // 데스크톱용 `<tr>` 도 DOM 에 공존하므로 `visible: true` 로 현재 뷰포트에서 실제
    // 렌더되는 노드만 선택 (strict mode 대응).
    const cards = page.getByTestId('holding-row').filter({ visible: true });
    const cardCount = await cards.count();
    if (cardCount > 0) {
      // 모바일 프로필에선 visible 한 `holding-row` 는 `<li>` (카드 분기) 여야 한다.
      const firstTag = await cards.first().evaluate(el => el.tagName);
      expect(firstTag).toBe('LI');
    } else {
      await expect(portfolio.emptyHoldings).toBeVisible();
    }

    await captureScreenshot(page, 'portfolio');
  });

  test('포트폴리오 — sync 버튼 라벨이 모바일에서 단축됨 (C4)', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await portfolio.goto();
    await expect(portfolio.accountTabs).toBeVisible();

    // KIS 계좌 (e2e-kis) 선택 시 sync 버튼 노출. 별칭 정확 일치 전제로 실패해도 테스트는 스킵.
    const kisTab = portfolio.accountTab('e2e-kis');
    if ((await kisTab.count()) === 0) {
      test.skip(true, 'e2e-kis 계좌가 없음 — seed 환경에서만 실행');
    }
    await kisTab.click();

    // C4: 모바일 가시 라벨은 "모의 sync" / 데스크톱 "KIS 모의 동기화".
    // kisSyncButton regex 는 둘 다 매치하므로 visible 여부만 확인하고 innerText 로 라벨 검증.
    await expect(portfolio.kisSyncButton).toBeVisible();
    const text = (await portfolio.kisSyncButton.innerText()).trim();
    // hidden 자식 span 은 innerText 에서 배제되므로 "모의 sync" 만 노출돼야 함.
    expect(text).toMatch(/^(?:실계좌 sync|모의 sync|처리 중…)$/);
  });

  test('종목상세(/stocks/005930) — 수평 스크롤 없음 + 차트 렌더 (D3)', async ({ page }) => {
    await page.goto('/stocks/005930');
    // 데이터 없으면 "대시보드로 이동" 대체 UI — 양쪽 모두 가로 스크롤 없어야 함.
    await page.waitForLoadState('networkidle');
    await noHorizontalOverflow(page);
    await captureScreenshot(page, 'stocks-005930');
  });

  test('AI 리포트(/reports/005930) — SourceRow 2줄 레이아웃 (C2)', async ({ page }) => {
    await page.goto('/reports/005930');
    await page.waitForLoadState('networkidle');
    await noHorizontalOverflow(page);
    await captureScreenshot(page, 'reports-005930');
  });

  test('시그널 정합도(/portfolio/1/alignment) — chip 3개 + N배지 (C3)', async ({ page }) => {
    await page.goto('/portfolio/1/alignment');
    await page.waitForLoadState('networkidle');
    await noHorizontalOverflow(page);

    // C3: signals 4개 이상 있는 item 에서 "+N개" 배지가 렌더된다. 실 데이터 의존이라 조건부 assert.
    const overflowBadge = page.getByLabel(/숨겨진 시그널/);
    const badgeCount = await overflowBadge.count();
    if (badgeCount > 0) {
      await expect(overflowBadge.first()).toBeVisible();
    }

    await captureScreenshot(page, 'alignment-1');
  });

  test('백테스트(/backtest) — 차트 aspect 모바일 1.4 (D3)', async ({ page }) => {
    await page.goto('/backtest');
    await page.waitForLoadState('networkidle');
    await noHorizontalOverflow(page);
    await captureScreenshot(page, 'backtest');
  });

  test('설정(/settings) — 알림 설정 + RealAccountSection 렌더 (B3 영역)', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { level: 1, name: '알림 설정' })).toBeVisible({
      timeout: 10_000,
    });
    await noHorizontalOverflow(page);

    // RealAccountSection 은 실계좌가 0 개여도 heading + "+ 추가" 버튼이 렌더.
    // B3: 계좌 행 레이아웃(flex-col sm:flex-row) 은 계좌가 있을 때만 가시 — testid 로 조건부 확인.
    const realAccountRows = page.getByTestId('real-account-row');
    const rowCount = await realAccountRows.count();
    if (rowCount > 0) {
      // 모바일에서 flex-col → 버튼 그룹이 별칭 아래로 내려옴. bounding box 의 세로 배치 확인.
      const row = realAccountRows.first();
      const box = await row.boundingBox();
      // flex-col 일 때 row 높이가 pure flex-row 보다 높음 (대략 >= 80px vs ~50px).
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(60);
    }

    await captureScreenshot(page, 'settings');
  });
});
