import { test, expect } from '@playwright/test';
import { AlignmentPage } from './pages/AlignmentPage';

test.describe('E. 에러 경로', () => {
  test('E1: 존재하지 않는 계좌 /portfolio/999/alignment → 에러 상태', async ({ page }) => {
    const alignment = new AlignmentPage(page);
    await alignment.goto(999);

    // API 에러 메시지 문구는 백엔드 detail에 따라 달라질 수 있어 텍스트 매칭 대신
    // "에러 상태의 구조적 특징"(로딩 끝 + empty state 없음 + 리포트 목록 없음)으로 검증.
    await page.waitForLoadState('networkidle');
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
    await expect(alignment.emptyState).toHaveCount(0);
    // 리포트 목록 ul(role="list") 중 시그널 정합도 카드 목록은 존재하지 않음
    await expect(page.locator('main ul[role="list"]')).toHaveCount(0);
  });

  test('E2: accounts API 네트워크 차단 → "계좌 조회 실패" 배너', async ({ page }) => {
    // 브라우저는 Next Route Handler 경유 → 실제 경로는 /api/admin/portfolio/accounts
    await page.route('**/api/admin/portfolio/accounts', route => route.abort());
    await page.goto('/portfolio');

    // role="alert" 는 Next route announcer 와 충돌 → 텍스트로 직접 매칭
    await expect(page.getByText(/계좌 조회 실패/)).toBeVisible({ timeout: 10_000 });
  });
});
