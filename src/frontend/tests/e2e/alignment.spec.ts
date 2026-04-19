import { test, expect } from '@playwright/test';
import { PortfolioPage } from './pages/PortfolioPage';
import { AlignmentPage } from './pages/AlignmentPage';

test.describe('D. 얼라인먼트 페이지', () => {
  test('D1: 포트폴리오에서 "시그널 정합도" 링크 → 얼라인먼트 페이지', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await portfolio.goto();
    await expect(portfolio.accountTabs).toBeVisible();
    await portfolio.alignmentLink.click();

    // 특정 계좌 id 에 의존하지 않도록 정수 매칭 — seed 순서에 따라 id 는 달라질 수 있음.
    await expect(page).toHaveURL(/\/portfolio\/\d+\/alignment$/);
  });

  test('D2: 페이지 헤더 — "시그널 정합도 (계좌 #1)"', async ({ page }) => {
    const alignment = new AlignmentPage(page);
    await alignment.goto(1);

    await expect(alignment.heading).toHaveText(/시그널 정합도 \(계좌 #1\)/);
    await expect(page.getByText(/최근 30일 · 스코어 60점 이상/)).toBeVisible();
  });

  test('D3: 보유 없는 계좌 → 빈 상태', async ({ page }) => {
    // 계좌 2(e2e-kis)는 holdings 가 비어있어 items=[] 는 항상 성립 (데이터 환경 독립).
    const alignment = new AlignmentPage(page);
    await alignment.goto(2);

    await expect(alignment.emptyState).toBeVisible();
  });

  test('D4: min_score 슬라이더 60→30 — 헤더 카피 갱신', async ({ page }) => {
    const alignment = new AlignmentPage(page);
    await alignment.goto(1);
    // 초기 상태는 시그널 유무에 따라 달라질 수 있으므로 슬라이더 조작 효과만 검증.
    await alignment.setMinScore(30);

    // 서브카피의 숫자 갱신 확인
    await expect(page.getByText(/최근 30일 · 스코어 30점 이상/)).toBeVisible();
    // 슬라이더 오른쪽 표시도 30
    await expect(alignment.minScoreSlider).toHaveValue('30');
  });

  test('D5: "← 포트폴리오" 링크 → /portfolio 복귀', async ({ page }) => {
    const alignment = new AlignmentPage(page);
    await alignment.goto(1);

    await alignment.backLink.click();
    await expect(page).toHaveURL(/\/portfolio$/);
  });

  test('D6: 유효하지 않은 accountId → 에러 박스', async ({ page }) => {
    await page.goto('/portfolio/abc/alignment');

    await expect(page.getByText('유효하지 않은 계좌 ID 입니다')).toBeVisible();
  });
});
