import { test, expect } from '@playwright/test';
import { HomePage } from './pages/HomePage';
import { PortfolioPage } from './pages/PortfolioPage';

test.describe('A. 내비게이션·접근성', () => {
  test('A1: 홈(/) 접근 — 타이틀·h1.sr-only', async ({ page }) => {
    const home = new HomePage(page);
    await home.goto();

    await expect(page).toHaveTitle(/SIGNAL.*공매도/);
    await expect(page.getByRole('heading', { level: 1, name: '시그널 대시보드' })).toBeAttached();
  });

  test('A2: NavHeader의 "포트폴리오" 클릭 → /portfolio + aria-current', async ({ page }) => {
    const home = new HomePage(page);
    await home.goto();
    await home.openPortfolio();

    await expect(page).toHaveURL(/\/portfolio$/);
    await expect(home.portfolioLink).toHaveAttribute('aria-current', 'page');
  });

  test('A3: 직접 /portfolio 진입 → 계좌 탭 2개 렌더', async ({ page }) => {
    const portfolio = new PortfolioPage(page);
    await portfolio.goto();

    await expect(portfolio.accountTabs).toBeVisible();
    await expect(portfolio.accountTab('e2e-manual')).toBeVisible();
    await expect(portfolio.accountTab('e2e-kis')).toBeVisible();
  });
});
